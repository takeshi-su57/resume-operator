"""Node: Analyze gaps between resume and job requirements."""

import logging
from typing import Any

from resume_operator.prompts.gap_analysis import ANALYZE_GAPS
from resume_operator.state import GapAnalysis, ResumeOptimizerState
from resume_operator.tools.json_parser import extract_json
from resume_operator.tools.llm_provider import get_llm

logger = logging.getLogger(__name__)


def analyze_gaps(state: ResumeOptimizerState) -> dict[str, Any]:
    """Identify gaps, strengths, and improvement suggestions.

    Uses ATS score results and full resume/job data to produce actionable
    suggestions for optimizing the resume content.
    """
    logger.info("analyze_gaps: starting")
    errors: list[str] = list(state.errors)

    # --- Call LLM with gap analysis prompt ---
    try:
        llm = get_llm()
        prompt = ANALYZE_GAPS.format(
            resume_json=state.resume.model_dump_json(),
            job_description=state.job_description.raw_text,
            ats_score=state.ats_score.score,
            keyword_gaps=state.ats_score.keyword_gaps,
        )
        logger.debug("analyze_gaps: LLM prompt: %s", prompt)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        logger.debug("analyze_gaps: LLM response: %s", content)
        parsed = extract_json(str(content))
    except ValueError as exc:
        logger.error("analyze_gaps: LLM returned invalid JSON: %s", exc)
        errors.append(f"analyze_gaps: LLM returned invalid JSON: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("analyze_gaps: LLM call failed: %s", exc)
        errors.append(f"analyze_gaps: LLM call failed: {exc}")
        return {"errors": errors}

    # --- Build GapAnalysis ---
    gap_analysis = GapAnalysis(
        gaps=parsed.get("gaps") or [],
        strengths=parsed.get("strengths") or [],
        suggestions=parsed.get("suggestions") or [],
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
