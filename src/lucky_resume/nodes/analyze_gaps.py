"""Node: Analyze gaps between resume and job requirements."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from lucky_resume.events import node_span
from lucky_resume.prompts.gap_analysis import ANALYZE_GAPS
from lucky_resume.state import GapAnalysis, ResumeOptimizerState
from lucky_resume.tools.llm_provider import get_structured_llm

logger = logging.getLogger(__name__)


class GapAnalysisLLMOutput(BaseModel):
    """Schema handed to `with_structured_output` — the LLM fills this in directly."""

    gaps: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


def analyze_gaps(state: ResumeOptimizerState) -> dict[str, Any]:
    """Identify gaps, strengths, and improvement suggestions.

    Uses ATS score results and full resume/job data to produce actionable
    suggestions for optimizing the resume content.
    """
    with node_span("analyze_gaps"):
        return _analyze_gaps_body(state)


def _analyze_gaps_body(state: ResumeOptimizerState) -> dict[str, Any]:
    logger.info("analyze_gaps: starting")
    errors: list[str] = list(state.errors)

    try:
        llm = get_structured_llm(GapAnalysisLLMOutput)
        prompt = ANALYZE_GAPS.format(
            resume_json=state.resume.model_dump_json(),
            job_description=state.job_description.raw_text,
            ats_score=state.ats_score.score,
            keyword_gaps=state.ats_score.keyword_gaps,
        )
        logger.debug("analyze_gaps: LLM prompt: %s", prompt)
        parsed: GapAnalysisLLMOutput = llm.invoke(prompt)
        logger.debug("analyze_gaps: LLM response: %s", parsed.model_dump_json())
    except ValidationError as exc:
        logger.error("analyze_gaps: LLM returned schema-invalid data: %s", exc)
        errors.append(f"analyze_gaps: LLM returned schema-invalid data: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("analyze_gaps: LLM call failed: %s", exc)
        errors.append(f"analyze_gaps: LLM call failed: {exc}")
        return {"errors": errors}

    gap_analysis = GapAnalysis(
        gaps=list(parsed.gaps),
        strengths=list(parsed.strengths),
        suggestions=list(parsed.suggestions),
    )

    logger.info(
        "analyze_gaps: completed — gaps=%d, strengths=%d, suggestions=%d",
        len(gap_analysis.gaps),
        len(gap_analysis.strengths),
        len(gap_analysis.suggestions),
    )

    result: dict[str, Any] = {"gap_analysis": gap_analysis}
    if errors != list(state.errors):
        result["errors"] = errors
    return result
