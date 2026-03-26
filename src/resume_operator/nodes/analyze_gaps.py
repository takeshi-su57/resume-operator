"""Node: Analyze gaps between resume and job requirements."""

from typing import Any

from resume_operator.state import ResumeOptimizerState


def analyze_gaps(state: ResumeOptimizerState) -> dict[str, Any]:
    """Identify gaps, strengths, and improvement suggestions.

    Uses ATS score results and full resume/job data to produce actionable
    suggestions for optimizing the resume content.
    """
    # TODO: Send resume + job + ats_score to LLM with prompts/gap_analysis.py template
    # TODO: Parse LLM JSON response into GapAnalysis fields
    return {}
