"""Prompt template for ATS compatibility scoring."""

ATS_SCORE = """Score how well this resume matches the job description for ATS compatibility.

Resume data:
{resume_json}

Job description:
{job_description}

Analyze keyword overlap, skills alignment, and experience relevance. Populate the
output schema — score in the range 0.0 (no match) to 1.0 (perfect match), plus a
short reasoning, concrete keyword matches, and concrete keyword gaps.
"""
