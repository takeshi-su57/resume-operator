"""Node: Score resume ATS compatibility against job description."""

from typing import Any

from resume_operator.state import ResumeOptimizerState


def ats_score(state: ResumeOptimizerState) -> dict[str, Any]:
    """Score how well the resume matches the job description for ATS systems.

    Compares resume keywords, experience, and skills against job requirements.
    Returns a score (0.0-1.0), keyword matches, keyword gaps, and reasoning.
    """
    # TODO: Send resume + job description to LLM with prompts/ats_scoring.py template
    # TODO: Parse LLM JSON response into ATSScore fields
    return {}
