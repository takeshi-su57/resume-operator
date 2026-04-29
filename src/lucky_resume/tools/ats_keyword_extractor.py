"""Extract the hard/soft skill comparison table for the #81 ATSReport.

One LLM call over both resume + JD returns a list of skill-count rows.
The orchestrator (`nodes/ats_score.py`) feeds these rows into
`ATSReport.hard_skills` / `soft_skills` and derives
`keyword_matches` / `keyword_gaps` for back-compat.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationError

from lucky_resume.prompts.ats_keywords import EXTRACT_ATS_KEYWORDS
from lucky_resume.state import SkillCountRow
from lucky_resume.tools.llm_provider import get_structured_llm

logger = logging.getLogger(__name__)


class _SkillCountLLM(BaseModel):
    """Mirror of SkillCountRow; separate so we validate LLM output before
    promoting to the state schema."""

    name: str
    resume_count: int = 0
    jd_count: int = 0


class ATSKeywordsLLMOutput(BaseModel):
    hard_skills: list[_SkillCountLLM] = Field(default_factory=list)
    soft_skills: list[_SkillCountLLM] = Field(default_factory=list)


# Hard caps per category — the prompt asks for 25 / 15, these trim if the LLM
# drifted. Protects the Rich table display and the composite score from
# dilution by long-tail near-zero rows.
MAX_HARD_SKILLS = 25
MAX_SOFT_SKILLS = 15


def extract_keywords(
    resume_text: str, jd_text: str
) -> tuple[list[SkillCountRow], list[SkillCountRow]]:
    """Return (hard_skills, soft_skills) for the #81 report. On any LLM
    failure, returns two empty lists — the orchestrator records the error
    and the composite score falls back to the structural dimensions alone.
    """
    if not resume_text.strip() or not jd_text.strip():
        logger.warning("extract_keywords: empty resume or JD text — returning empty tables")
        return [], []

    try:
        llm = get_structured_llm(ATSKeywordsLLMOutput)
        prompt = EXTRACT_ATS_KEYWORDS.format(resume_text=resume_text, jd_text=jd_text)
        logger.debug("extract_keywords: LLM prompt: %s", prompt)
        parsed: ATSKeywordsLLMOutput = llm.invoke(prompt)
        logger.debug("extract_keywords: LLM response: %s", parsed.model_dump_json())
    except ValidationError as exc:
        logger.error("extract_keywords: LLM returned schema-invalid data: %s", exc)
        return [], []
    except Exception as exc:
        logger.error("extract_keywords: LLM call failed: %s", exc)
        return [], []

    hard = _promote(parsed.hard_skills[:MAX_HARD_SKILLS])
    soft = _promote(parsed.soft_skills[:MAX_SOFT_SKILLS])
    logger.info(
        "extract_keywords: completed — hard=%d, soft=%d",
        len(hard),
        len(soft),
    )
    return hard, soft


def _promote(rows: list[_SkillCountLLM]) -> list[SkillCountRow]:
    """Promote LLM-side rows to state-side rows, clamping negatives to 0."""
    out: list[SkillCountRow] = []
    for r in rows:
        name = r.name.strip()
        if not name:
            continue
        out.append(
            SkillCountRow(
                name=name,
                resume_count=max(0, r.resume_count),
                jd_count=max(0, r.jd_count),
            )
        )
    return out


def derive_matches_and_gaps(
    hard: list[SkillCountRow], soft: list[SkillCountRow]
) -> tuple[list[str], list[str]]:
    """Back-compat helper — flatten the tables into the simple
    `keyword_matches` / `keyword_gaps` lists the pre-#81 ATSScore exposed.

    A skill is a "match" when both sides have ≥1 mention; a "gap" when
    the JD asks for it (jd_count ≥ 1) but the resume doesn't (resume_count == 0).
    """
    matches: list[str] = []
    gaps: list[str] = []
    for row in (*hard, *soft):
        if row.jd_count >= 1 and row.resume_count >= 1:
            matches.append(row.name)
        elif row.jd_count >= 1 and row.resume_count == 0:
            gaps.append(row.name)
    return matches, gaps
