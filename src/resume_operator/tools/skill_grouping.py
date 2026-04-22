"""Propose a skill-group categorization from a flat skill list via LLM.

Used by the bootstrap interview (#70) when the user has flat `skills` but no
`skill_groups` yet — the LLM proposes a grouping, the user accepts / edits /
rejects. On reject, the master falls back to the flat list; on accept, the
groups replace the flat rendering in the SKILLS section.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.skill_grouping import PROPOSE_SKILL_GROUPS
from resume_operator.state import SkillGroup
from resume_operator.tools.llm_provider import get_structured_llm

logger = logging.getLogger(__name__)


class SkillGroupLLM(BaseModel):
    category: str = ""
    items: list[str] = Field(default_factory=list)


class SkillGroupsLLMOutput(BaseModel):
    groups: list[SkillGroupLLM] = Field(default_factory=list)


def propose_groups(skills: list[str]) -> list[SkillGroup]:
    """Ask the LLM to categorise a flat skill list. Returns `[]` on failure.

    The helper drops groups the LLM returned with empty items, filters items
    not present in the original input (fabrication guard), and de-dupes so
    every input skill ends up in at most one group.
    """
    if not skills:
        return []

    prompt = PROPOSE_SKILL_GROUPS.format(skills=", ".join(skills))
    try:
        llm = get_structured_llm(SkillGroupsLLMOutput)
        parsed: SkillGroupsLLMOutput = llm.invoke(prompt)
    except ValidationError as exc:
        logger.error("propose_groups: LLM returned schema-invalid data: %s", exc)
        return []
    except Exception as exc:
        logger.error("propose_groups: LLM call failed: %s", exc)
        return []

    allowed = {s: None for s in skills}  # preserves input casing
    seen: set[str] = set()
    result: list[SkillGroup] = []
    for group in parsed.groups:
        if not group.category.strip():
            continue
        filtered: list[str] = []
        for item in group.items:
            # The LLM sometimes re-casings an item; normalise against the allowlist.
            canonical = _match_original(item, allowed)
            if canonical is None:
                logger.warning(
                    "propose_groups: rejected fabricated skill %r (not in input list)", item
                )
                continue
            if canonical in seen:
                continue
            seen.add(canonical)
            filtered.append(canonical)
        if filtered:
            result.append(SkillGroup(category=group.category.strip(), items=filtered))

    # Any input skills the LLM didn't place get collected into "Other" so the
    # user doesn't silently lose them.
    leftovers = [s for s in skills if s not in seen]
    if leftovers:
        result.append(SkillGroup(category="Other", items=leftovers))

    logger.info(
        "propose_groups: grouped %d skills into %d categories",
        sum(len(g.items) for g in result),
        len(result),
    )
    return result


def _match_original(item: str, allowed: dict[str, None]) -> str | None:
    """Canonicalise an LLM-returned item against the input allowlist (case-insensitive)."""
    if item in allowed:
        return item
    lowered = item.lower()
    for original in allowed:
        if original.lower() == lowered:
            return original
    return None
