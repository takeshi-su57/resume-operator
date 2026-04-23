"""Node: Generate LLM proposals the user gates in the approval flow.

Each loop iteration of #78 calls this node after `optimize_content` has
produced a tailored version the user wasn't satisfied with. The node sees
the current tailored output, the source menu, the JD's remaining gaps, and
the per-run `rejected_suggestions` list, and emits a short list of concrete
edits — `rewrite_master`, `rewrite_fact`, or `new_fact` — each grounded in
an existing source_id so the user has something to reality-check against.

Two public entry points:

  - `propose_changes` — the LangGraph node; reads state, writes
    `state.proposals`.

  - `revise_proposal` — the Fix-loop helper; called by `approval_flow` when
    the user asks for a revision. Takes one proposal + user feedback and
    returns one revised proposal. Not wired into the graph — it's invoked
    directly by the approval UX between proposal presentations.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.propose_changes import PROPOSE_CHANGES, REVISE_PROPOSAL
from resume_operator.state import (
    Proposal,
    RejectedSuggestion,
    ResumeOptimizerState,
    TailoredResume,
)
from resume_operator.tools.llm_provider import get_structured_llm
from resume_operator.tools.source_index import SourceIndex, build_source_index

logger = logging.getLogger(__name__)


# Soft guard — the prompt says "at most 5" but LLMs drift; we hard-trim on the
# node side so the approval UX doesn't drown the user.
MAX_PROPOSALS_PER_ITERATION = 5


class ProposalLLM(BaseModel):
    """Schema the LLM fills in. Mirrors `state.Proposal` but separate so the
    node validates + coerces before building the real `Proposal` objects."""

    kind: str = "new_fact"
    grounding_source_id: str
    original_text: str = ""
    proposed_text: str
    rationale: str = ""
    target_role_id: str = ""


class ProposeChangesLLMOutput(BaseModel):
    proposals: list[ProposalLLM] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def propose_changes(state: ResumeOptimizerState) -> dict[str, Any]:
    """Emit `state.proposals` for the approval flow to gate (#78)."""
    logger.info("propose_changes: starting (iteration=%d)", state.current_iteration)
    errors: list[str] = list(state.errors)

    index = build_source_index(state.master, state.facts)
    if not index.entries:
        logger.warning("propose_changes: empty source index — skipping")
        errors.append("propose_changes: source index is empty")
        return {"errors": errors, "proposals": []}

    try:
        llm = get_structured_llm(ProposeChangesLLMOutput)
        prompt = PROPOSE_CHANGES.format(
            source_menu=index.as_prompt_menu(),
            job_description=state.job_description.raw_text,
            tailored_summary=state.tailored_resume.tailored_summary or "(no summary yet)",
            kept_items=_kept_items_block(state.tailored_resume),
            keyword_gaps=", ".join(state.ats_score.keyword_gaps) or "(none captured)",
            suggestions=_bulleted(state.gap_analysis.suggestions),
            rejected_block=_rejected_block(state.rejected_suggestions),
        )
        logger.debug("propose_changes: LLM prompt: %s", prompt)
        parsed: ProposeChangesLLMOutput = llm.invoke(prompt)
        logger.debug("propose_changes: LLM response: %s", parsed.model_dump_json())
    except ValidationError as exc:
        logger.error("propose_changes: LLM returned schema-invalid data: %s", exc)
        errors.append(f"propose_changes: LLM returned schema-invalid data: {exc}")
        return {"errors": errors, "proposals": []}
    except Exception as exc:
        logger.error("propose_changes: LLM call failed: %s", exc)
        errors.append(f"propose_changes: LLM call failed: {exc}")
        return {"errors": errors, "proposals": []}

    validated, rejected_ids = _validate_and_build(parsed.proposals, index)
    for sid in rejected_ids:
        msg = f"propose_changes: rejected fabricated grounding_source_id: {sid}"
        logger.error(msg)
        errors.append(msg)

    trimmed = validated[:MAX_PROPOSALS_PER_ITERATION]
    logger.info(
        "propose_changes: completed — proposals=%d (rewrite_master=%d, rewrite_fact=%d, "
        "new_fact=%d), dropped_fabricated=%d, trimmed_to=%d",
        len(validated),
        sum(1 for p in trimmed if p.kind == "rewrite_master"),
        sum(1 for p in trimmed if p.kind == "rewrite_fact"),
        sum(1 for p in trimmed if p.kind == "new_fact"),
        len(rejected_ids),
        len(trimmed),
    )

    result: dict[str, Any] = {"proposals": trimmed}
    if errors != list(state.errors):
        result["errors"] = errors
    return result


def revise_proposal(
    state: ResumeOptimizerState, original: Proposal, user_feedback: str
) -> Proposal | None:
    """Fix-loop entry point. Takes one proposal + user feedback, returns a
    single revised proposal — or `None` when the LLM call fails (the caller
    treats that as "keep the original, let the user re-decide").

    Deliberately not a LangGraph node — the Fix loop happens inside
    `approval_flow` between individual proposal presentations, not between
    graph nodes.
    """
    logger.info("revise_proposal: revising %s", original.grounding_source_id)
    index = build_source_index(state.master, state.facts)

    try:
        llm = get_structured_llm(ProposalLLM)
        prompt = REVISE_PROPOSAL.format(
            kind=original.kind,
            grounding_source_id=original.grounding_source_id,
            original_text=original.original_text,
            proposed_text=original.proposed_text,
            rationale=original.rationale,
            user_feedback=user_feedback,
            job_description=state.job_description.raw_text,
            source_menu=index.as_prompt_menu(),
        )
        parsed: ProposalLLM = llm.invoke(prompt)
    except (ValidationError, Exception) as exc:
        logger.error("revise_proposal: LLM call failed: %s", exc)
        return None

    validated, _ = _validate_and_build([parsed], index)
    if not validated:
        logger.warning(
            "revise_proposal: revised grounding_source_id %r not in index — returning None",
            parsed.grounding_source_id,
        )
        return None
    return validated[0]


# --- helpers --------------------------------------------------------------


def _validate_and_build(
    raw: list[ProposalLLM], index: SourceIndex
) -> tuple[list[Proposal], list[str]]:
    """Drop proposals whose grounding ID isn't in the index; coerce kind to the
    allowed set; anchor `original_text` to the canonical menu text so the UX
    doesn't display an LLM paraphrase."""
    kept: list[Proposal] = []
    rejected: list[str] = []
    allowed_kinds = {"rewrite_master", "rewrite_fact", "new_fact"}
    for r in raw:
        entry = index.get(r.grounding_source_id)
        if entry is None:
            rejected.append(r.grounding_source_id)
            continue
        if not r.proposed_text.strip():
            # Silently drop proposals with empty text — not worth surfacing to the user.
            continue
        kind = r.kind.lower().strip()
        if kind not in allowed_kinds:
            kind = _infer_kind(r.grounding_source_id)
        # Echo the canonical text for rewrite kinds; leave empty for new_fact unless
        # the LLM explicitly paraphrased the grounding.
        original_text = entry.text if kind != "new_fact" else r.original_text.strip()
        kept.append(
            Proposal(
                kind=kind,
                grounding_source_id=r.grounding_source_id,
                original_text=original_text,
                proposed_text=r.proposed_text.strip(),
                rationale=r.rationale.strip(),
                target_role_id=r.target_role_id.strip(),
            )
        )
    return kept, rejected


def _infer_kind(source_id: str) -> str:
    """Fallback kind inference when the LLM picks something outside the allowed set."""
    if source_id.startswith("master:"):
        return "rewrite_master"
    if source_id.startswith("facts:"):
        return "rewrite_fact"
    return "new_fact"


def _kept_items_block(tailored: TailoredResume) -> str:
    lines: list[str] = []
    for item in tailored.kept_or_reworded():
        text = item.new_text or item.original_text
        lines.append(f"- [{item.source_id}] ({item.action}) {text}")
    return "\n".join(lines) if lines else "(none)"


def _bulleted(items: list[str]) -> str:
    return "\n".join(f"- {s}" for s in items) if items else "(none)"


def _rejected_block(rejected: list[RejectedSuggestion]) -> str:
    if not rejected:
        return "(none — first pass, or the user has accepted/refined everything so far)"
    lines: list[str] = []
    for r in rejected:
        reason = r.user_reason or "(no reason given)"
        lines.append(
            f"- kind={r.kind} grounded_at={r.grounding_source_id}\n"
            f"  rejected_text: {r.rejected_text}\n"
            f"  user_reason: {reason}"
        )
    return "\n".join(lines)
