"""Node: Score resume ATS compatibility against job description."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.ats_scoring import ATS_SCORE
from resume_operator.state import ATSScore, ResumeOptimizerState
from resume_operator.tools.llm_provider import get_structured_llm

logger = logging.getLogger(__name__)


class ATSScoreLLMOutput(BaseModel):
    """Schema handed to `with_structured_output` — the LLM fills this in directly."""

    score: float = Field(..., description="ATS compatibility score, 0.0 to 1.0")
    reasoning: str = Field(..., description="Short justification of the score")
    keyword_matches: list[str] = Field(default_factory=list)
    keyword_gaps: list[str] = Field(default_factory=list)


def ats_score(state: ResumeOptimizerState) -> dict[str, Any]:
    """Score how well the resume matches the job description for ATS systems.

    Compares resume keywords, experience, and skills against job requirements.
    Returns a score (0.0-1.0), keyword matches, keyword gaps, and reasoning.
    """
    logger.info("ats_score: starting")
    errors: list[str] = list(state.errors)

    if not state.resume.raw_text:
        logger.warning("ats_score: skipping — resume data is empty (parse_resume may have failed)")
        errors.append("ats_score: skipping — resume data is empty")
        return {"errors": errors}

    try:
        llm = get_structured_llm(ATSScoreLLMOutput)
        prompt = ATS_SCORE.format(
            resume_json=state.resume.model_dump_json(),
            job_description=state.job_description.raw_text,
        )
        logger.debug("ats_score: LLM prompt: %s", prompt)
        parsed: ATSScoreLLMOutput = llm.invoke(prompt)
        logger.debug("ats_score: LLM response: %s", parsed.model_dump_json())
    except ValidationError as exc:
        logger.error("ats_score: LLM returned schema-invalid data: %s", exc)
        errors.append(f"ats_score: LLM returned schema-invalid data: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("ats_score: LLM call failed: %s", exc)
        errors.append(f"ats_score: LLM call failed: {exc}")
        return {"errors": errors}

    score = max(0.0, min(1.0, float(parsed.score)))
    result_score = ATSScore(
        score=score,
        reasoning=parsed.reasoning,
        keyword_matches=list(parsed.keyword_matches),
        keyword_gaps=list(parsed.keyword_gaps),
    )

    logger.info(
        "ats_score: completed — score=%.2f, matches=%d, gaps=%d",
        result_score.score,
        len(result_score.keyword_matches),
        len(result_score.keyword_gaps),
    )

    result: dict[str, Any] = {"ats_score": result_score}
    if errors != list(state.errors):
        result["errors"] = errors
    return result
