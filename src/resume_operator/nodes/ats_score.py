"""Node: Score resume ATS compatibility against job description."""

import json
import logging
from typing import Any

from resume_operator.prompts.ats_scoring import ATS_SCORE
from resume_operator.state import ATSScore, ResumeOptimizerState
from resume_operator.tools.llm_provider import get_llm

logger = logging.getLogger(__name__)


def ats_score(state: ResumeOptimizerState) -> dict[str, Any]:
    """Score how well the resume matches the job description for ATS systems.

    Compares resume keywords, experience, and skills against job requirements.
    Returns a score (0.0-1.0), keyword matches, keyword gaps, and reasoning.
    """
    logger.info("ats_score: starting")
    errors: list[str] = list(state.errors)

    # --- Call LLM with ATS scoring prompt ---
    try:
        llm = get_llm()
        prompt = ATS_SCORE.format(
            resume_json=state.resume.model_dump_json(),
            job_description=state.job_description.raw_text,
        )
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(str(content))
    except json.JSONDecodeError as exc:
        logger.error("ats_score: LLM returned invalid JSON: %s", exc)
        errors.append(f"ats_score: LLM returned invalid JSON: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("ats_score: LLM call failed: %s", exc)
        errors.append(f"ats_score: LLM call failed: {exc}")
        return {"errors": errors}

    # --- Build ATSScore ---
    raw_score = float(parsed.get("score", 0.0) or 0.0)
    score = max(0.0, min(1.0, raw_score))
    result_score = ATSScore(
        score=score,
        reasoning=parsed.get("reasoning") or "",
        keyword_matches=parsed.get("keyword_matches") or [],
        keyword_gaps=parsed.get("keyword_gaps") or [],
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
