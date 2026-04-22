"""Node: Tailor resume content per-item against the job description.

This node produces a `TailoredResume` — a list of `TailoredItem` decisions,
each referencing a stable source ID from the master resume or facts bank.
The fabrication guard rejects any `source_id` not present in the
`SourceIndex`; the LLM cannot invent text that isn't traceable back to a
source.

For back-compat with #027 (not yet landed), it also populates the legacy
`OptimizedResume.sections` string blob, derived from the tailored items
grouped by kind.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.content_optimization import OPTIMIZE_CONTENT
from resume_operator.state import (
    OptimizedResume,
    ResumeOptimizerState,
    TailoredItem,
    TailoredResume,
)
from resume_operator.tools.llm_provider import get_structured_llm
from resume_operator.tools.source_index import SourceIndex, build_source_index

logger = logging.getLogger(__name__)


class TailoredItemLLM(BaseModel):
    source_id: str
    action: str = "keep"  # keep | reword | drop
    original_text: str = ""
    new_text: str = ""


class TailoredResumeLLMOutput(BaseModel):
    tailored_summary: str = ""  # fresh JD-crafted SUMMARY text — not sourced from the items list
    tailored_headline: str = ""  # fresh JD-crafted tagline under the name (#70)
    items: list[TailoredItemLLM] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def optimize_content(state: ResumeOptimizerState) -> dict[str, Any]:
    """Produce a `TailoredResume` — per-item decisions over master + facts."""
    logger.info("optimize_content: starting")
    errors: list[str] = list(state.errors)

    index = build_source_index(state.master, state.facts)

    if not index.entries:
        logger.warning("optimize_content: empty source index — skipping")
        errors.append("optimize_content: source index is empty")
        return {"errors": errors}

    try:
        llm = get_structured_llm(TailoredResumeLLMOutput)
        prompt = OPTIMIZE_CONTENT.format(
            source_menu=index.as_prompt_menu(),
            job_description=state.job_description.raw_text,
            gap_analysis=state.gap_analysis.model_dump_json(),
        )
        logger.debug("optimize_content: LLM prompt: %s", prompt)
        parsed: TailoredResumeLLMOutput = llm.invoke(prompt)
        logger.debug("optimize_content: LLM response: %s", parsed.model_dump_json())
    except ValidationError as exc:
        logger.error("optimize_content: LLM returned schema-invalid data: %s", exc)
        errors.append(f"optimize_content: LLM returned schema-invalid data: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("optimize_content: LLM call failed: %s", exc)
        errors.append(f"optimize_content: LLM call failed: {exc}")
        return {"errors": errors}

    # --- Fabrication guard ---
    validated_items, rejected = _validate_items(parsed.items, index)
    for ref in rejected:
        msg = f"optimize_content: rejected fabricated source_id: {ref}"
        logger.error(msg)
        errors.append(msg)

    tailored = TailoredResume(
        items=validated_items,
        notes=list(parsed.notes),
        tailored_summary=parsed.tailored_summary.strip(),
        tailored_headline=parsed.tailored_headline.strip(),
    )
    optimized_legacy = _project_to_sections(tailored, index)

    logger.info(
        "optimize_content: completed — items=%d (kept=%d, reworded=%d, dropped=%d), "
        "fabricated_rejected=%d, notes=%d, summary=%s, headline=%s",
        len(tailored.items),
        sum(1 for i in tailored.items if i.action == "keep"),
        sum(1 for i in tailored.items if i.action == "reword"),
        sum(1 for i in tailored.items if i.action == "drop"),
        len(rejected),
        len(tailored.notes),
        "yes" if tailored.tailored_summary else "no",
        "yes" if tailored.tailored_headline else "no",
    )

    result: dict[str, Any] = {
        "tailored_resume": tailored,
        "optimized_resume": optimized_legacy,
    }
    if errors != list(state.errors):
        result["errors"] = errors
    return result


def _validate_items(
    items: list[TailoredItemLLM], index: SourceIndex
) -> tuple[list[TailoredItem], list[str]]:
    """Drop items whose `source_id` isn't in the index; return (kept, rejected_ids)."""
    kept: list[TailoredItem] = []
    rejected: list[str] = []
    for raw in items:
        entry = index.get(raw.source_id)
        if entry is None:
            rejected.append(raw.source_id)
            continue
        action = raw.action.lower()
        if action not in {"keep", "reword", "drop"}:
            action = "keep"
        # Always use the canonical text from the index as `original_text` — the LLM
        # sometimes paraphrases the echo. For `new_text`, trust the LLM only when action == reword.
        new_text = raw.new_text.strip() if action == "reword" else ""
        kept.append(
            TailoredItem(
                source_id=raw.source_id,
                action=action,
                original_text=entry.text,
                new_text=new_text,
            )
        )
    return kept, rejected


def _project_to_sections(tailored: TailoredResume, index: SourceIndex) -> OptimizedResume:
    """Back-compat projection: build the legacy `OptimizedResume.sections` blob so
    `generate_pdf` keeps working until #027 migrates it off the blob shape.
    """
    buckets: dict[str, list[str]] = {
        "summary": [],
        "experience": [],
        "skills": [],
        "education": [],
    }
    # Tailored summary wins over any kept `master:summary` item (issue #66).
    if tailored.tailored_summary:
        buckets["summary"].append(tailored.tailored_summary)
    for item in tailored.kept_or_reworded():
        text = item.new_text or item.original_text
        entry = index.get(item.source_id)
        if entry is None:
            continue
        if entry.kind == "summary":
            if tailored.tailored_summary:
                # Skip — the dedicated field already carried the summary above.
                continue
            buckets["summary"].append(text)
        elif entry.kind in {"experience-header", "experience-bullet"} or entry.kind.startswith(
            "extra-bullet"
        ):
            buckets["experience"].append(f"- {text}")
        elif entry.kind == "education":
            buckets["education"].append(text)
        elif entry.kind == "skill":
            buckets["skills"].append(text)
        elif entry.kind == "certification":
            buckets["skills"].append(f"Cert: {text}")
        elif entry.kind == "project":
            buckets["experience"].append(f"- Project: {text}")

    sections = {name: "\n".join(lines) for name, lines in buckets.items() if lines}
    changes_made = [f"{item.action}: {item.source_id}" for item in tailored.items]
    return OptimizedResume(sections=sections, changes_made=changes_made)
