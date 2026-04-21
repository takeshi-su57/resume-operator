"""Node: Optimize resume content based on gap analysis."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.content_optimization import OPTIMIZE_CONTENT
from resume_operator.state import OptimizedResume, ResumeOptimizerState
from resume_operator.tools.llm_provider import get_structured_llm

logger = logging.getLogger(__name__)


class OptimizedSections(BaseModel):
    """Named resume sections the optimizer writes. Fixed keys so the JSON
    schema is compatible with OpenAI's strict mode (every property required).
    """

    summary: str = ""
    experience: str = ""
    skills: str = ""
    education: str = ""


class OptimizedResumeLLMOutput(BaseModel):
    """Schema handed to `with_structured_output` — the LLM fills this in directly."""

    sections: OptimizedSections = Field(default_factory=OptimizedSections)
    changes_made: list[str] = Field(default_factory=list)


def optimize_content(state: ResumeOptimizerState) -> dict[str, Any]:
    """Rewrite and enhance resume content to better match the job description.

    Takes the original resume, gap analysis, and job description to produce
    optimized resume sections with tracked changes.
    """
    logger.info("optimize_content: starting")
    errors: list[str] = list(state.errors)

    try:
        llm = get_structured_llm(OptimizedResumeLLMOutput)
        prompt = OPTIMIZE_CONTENT.format(
            resume_json=state.resume.model_dump_json(),
            facts_json=state.facts.model_dump_json(),
            job_description=state.job_description.raw_text,
            gap_analysis=state.gap_analysis.model_dump_json(),
        )
        logger.debug("optimize_content: LLM prompt: %s", prompt)
        parsed: OptimizedResumeLLMOutput = llm.invoke(prompt)
        logger.debug("optimize_content: LLM response: %s", parsed.model_dump_json())
    except ValidationError as exc:
        logger.error("optimize_content: LLM returned schema-invalid data: %s", exc)
        errors.append(f"optimize_content: LLM returned schema-invalid data: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("optimize_content: LLM call failed: %s", exc)
        errors.append(f"optimize_content: LLM call failed: {exc}")
        return {"errors": errors}

    optimized_resume = OptimizedResume(
        sections=parsed.sections.model_dump(exclude_defaults=False),
        changes_made=list(parsed.changes_made),
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
