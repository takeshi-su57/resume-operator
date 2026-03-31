"""Node: Optimize resume content based on gap analysis."""

import logging
from typing import Any

from resume_operator.prompts.content_optimization import OPTIMIZE_CONTENT
from resume_operator.state import OptimizedResume, ResumeOptimizerState
from resume_operator.tools.json_parser import extract_json
from resume_operator.tools.llm_provider import get_llm

logger = logging.getLogger(__name__)


def optimize_content(state: ResumeOptimizerState) -> dict[str, Any]:
    """Rewrite and enhance resume content to better match the job description.

    Takes the original resume, gap analysis, and job description to produce
    optimized resume sections with tracked changes.
    """
    logger.info("optimize_content: starting")
    errors: list[str] = list(state.errors)

    # --- Call LLM with content optimization prompt ---
    try:
        llm = get_llm()
        prompt = OPTIMIZE_CONTENT.format(
            resume_json=state.resume.model_dump_json(),
            job_description=state.job_description.raw_text,
            gap_analysis=state.gap_analysis.model_dump_json(),
        )
        logger.debug("optimize_content: LLM prompt: %s", prompt)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        logger.debug("optimize_content: LLM response: %s", content)
        parsed = extract_json(str(content))
    except ValueError as exc:
        logger.error("optimize_content: LLM returned invalid JSON: %s", exc)
        errors.append(f"optimize_content: LLM returned invalid JSON: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("optimize_content: LLM call failed: %s", exc)
        errors.append(f"optimize_content: LLM call failed: {exc}")
        return {"errors": errors}

    # --- Build OptimizedResume ---
    optimized_resume = OptimizedResume(
        sections=parsed.get("sections") or {},
        changes_made=parsed.get("changes_made") or [],
    )

    logger.info(
        "optimize_content: completed — sections=%d, changes=%d",
        len(optimized_resume.sections),
        len(optimized_resume.changes_made),
    )

    result: dict[str, Any] = {"optimized_resume": optimized_resume}
    if errors != list(state.errors):
        result["errors"] = errors
    return result
