"""Node: Persist the user's approved proposals to facts_bank.yaml.

Runs at the end of each approval iteration in the #78 loop. Takes
`state.approved_proposals` and routes each `Proposal` into the right
facts-bank bucket:

  - `rewrite_master` → new `FactItem` in `extra_bullets` (or `projects`
    when the grounding isn't an experience bullet) with `overrides` set
    to the grounded master source_id, so the next tailor iteration's
    `build_source_index` hides the original master entry.

  - `rewrite_fact` → *replaces* the existing `FactItem` with the polished
    text. Same id is reused so `build_source_index` identity is stable.

  - `new_fact` → brand-new `FactItem` in `extra_bullets` (if
    `target_role_id` is set) or `projects` (otherwise). No `overrides`
    set — this is a net addition, not a shadow.

After writing, the node also refreshes `state.facts` in memory so the
next loop iteration's `propose_changes` / `optimize_content` pass sees
the updated bank without a re-load round-trip.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from resume_operator.state import FactItem, FactsBank, Proposal, ResumeOptimizerState
from resume_operator.tools.facts_bank import load_facts, save_facts

logger = logging.getLogger(__name__)


def apply_approvals(state: ResumeOptimizerState) -> dict[str, Any]:
    """Drain `state.approved_proposals` into `facts_bank.yaml` (#78)."""
    logger.info(
        "apply_approvals: starting — approved=%d",
        len(state.approved_proposals),
    )
    errors: list[str] = list(state.errors)

    if not state.approved_proposals:
        logger.info("apply_approvals: nothing to apply — skipping")
        return {"approved_proposals": []}

    if not state.facts_path:
        msg = "apply_approvals: no facts_path configured — cannot persist approvals"
        logger.error(msg)
        errors.append(msg)
        return {"errors": errors, "approved_proposals": []}

    facts_path = Path(state.facts_path)
    # Start from the on-disk bank, merge the in-memory state on top — in case the
    # file was edited between runs — then apply approvals.
    bank = load_facts(facts_path) if facts_path.exists() else FactsBank(**state.facts.model_dump())
    existing_ids = _collect_ids(bank)
    mint_id = _make_id_minter(existing_ids, today=date.today())

    rewrites = 0
    new_items = 0
    new_skills = 0
    skipped = 0
    for proposal in state.approved_proposals:
        if proposal.kind == "rewrite_fact":
            if _apply_rewrite_fact(bank, proposal):
                rewrites += 1
            else:
                skipped += 1
                logger.warning(
                    "apply_approvals: rewrite_fact grounded at %r not found in bank — skipped",
                    proposal.grounding_source_id,
                )
            continue

        if proposal.kind == "new_skill":
            # Bare skill name → `skills_beyond_master` (flat list). Dedupe by exact
            # match so re-approving the same skill across runs doesn't grow noise.
            skill = proposal.proposed_text.strip()
            if not skill:
                skipped += 1
                continue
            if skill in bank.skills_beyond_master or skill in _flatten_master_skills(state):
                logger.info(
                    "apply_approvals: skill %r already present — not re-adding",
                    skill,
                )
                skipped += 1
                continue
            bank.skills_beyond_master.append(skill)
            new_skills += 1
            continue

        # rewrite_master + new_fact both create new entries; rewrite_master carries
        # `overrides` so the source_index hides the shadowed master entry.
        fact = _build_new_fact_item(proposal, id_fn=mint_id)
        target_bucket = _bucket_for(proposal)
        if target_bucket == "extra_bullets":
            bank.extra_bullets.append(fact)
        else:
            bank.projects.append(fact)
        new_items += 1

    save_facts(bank, facts_path)
    logger.info(
        "apply_approvals: completed — rewrites=%d, new_items=%d, new_skills=%d, "
        "skipped=%d, facts_path=%s",
        rewrites,
        new_items,
        new_skills,
        skipped,
        facts_path,
    )

    return {
        # Clear the approved bucket so the next iteration starts empty.
        "approved_proposals": [],
        # Refresh in-memory facts so the next iteration sees the additions.
        "facts": bank,
    }


# --- helpers --------------------------------------------------------------


def _collect_ids(bank: FactsBank) -> set[str]:
    return {fi.id for fi in (*bank.projects, *bank.extra_bullets)}


def _flatten_master_skills(state: ResumeOptimizerState) -> set[str]:
    """Every skill the master already lists — used to dedupe `new_skill` approvals."""
    return set(state.master.all_skills()) if state.master else set()


def _make_id_minter(existing: set[str], *, today: date) -> Callable[[], str]:
    """Return a zero-arg callable that mints `approved-YYYYMMDD-{n}` ids without collisions."""
    used = set(existing)
    prefix = f"approved-{today.strftime('%Y%m%d')}"

    def _mint() -> str:
        for n in range(1, 1000):
            candidate = f"{prefix}-{n}"
            if candidate not in used:
                used.add(candidate)
                return candidate
        raise RuntimeError("apply_approvals: exhausted id suffixes 1..999")

    return _mint


def _build_new_fact_item(proposal: Proposal, *, id_fn: Callable[[], str]) -> FactItem:
    """Create a fresh `FactItem` from a `rewrite_master` or `new_fact` proposal."""
    overrides = proposal.grounding_source_id if proposal.kind == "rewrite_master" else ""
    role_id = proposal.target_role_id or _role_id_from_grounding(proposal.grounding_source_id)
    return FactItem(
        id=id_fn(),
        text=proposal.proposed_text,
        role_id=role_id,
        overrides=overrides,
        source=f"approved {date.today().isoformat()}",
    )


def _role_id_from_grounding(source_id: str) -> str:
    """Derive the role_id from a `master:exp-2-b3` or `master:exp-2` grounding.

    Returns `exp-2` for either shape. For non-experience groundings (education,
    skills, summary, facts:*) returns an empty string so the fact lands in the
    `projects` bucket rather than under a specific role.
    """
    if not source_id.startswith("master:"):
        return ""
    body = source_id[len("master:") :]
    if not body.startswith("exp-"):
        return ""
    return body.rsplit("-b", 1)[0] if "-b" in body else body


def _bucket_for(proposal: Proposal) -> str:
    """Pick the facts-bank bucket for a newly created item.

    Items pinned to a role go under `extra_bullets`; standalone items go under
    `projects`. `rewrite_master` groundings that point at an experience bullet
    or header naturally carry a role_id; `new_fact` relies on the LLM's
    `target_role_id`.
    """
    if proposal.target_role_id:
        return "extra_bullets"
    if proposal.kind == "rewrite_master" and proposal.grounding_source_id.startswith("master:exp-"):
        return "extra_bullets"
    return "projects"


def _apply_rewrite_fact(bank: FactsBank, proposal: Proposal) -> bool:
    """Replace an existing fact's text with the polished version.

    Grounding source_id is `facts:<id>`. Mutates the bank in place. Returns
    True when the target was found, False when the grounded id no longer
    exists (user deleted it between runs).
    """
    if not proposal.grounding_source_id.startswith("facts:"):
        return False
    fact_id = proposal.grounding_source_id[len("facts:") :]
    for candidate in (*bank.projects, *bank.extra_bullets):
        if candidate.id == fact_id:
            candidate.text = proposal.proposed_text
            candidate.source = f"approved {date.today().isoformat()}"
            return True
    return False
