"""Prompt template for resume gap analysis."""

ANALYZE_GAPS = """Analyze gaps between this resume and the job requirements.

Resume data:
{resume_json}

Job description:
{job_description}

ATS score: {ats_score}
Keyword gaps: {keyword_gaps}

Identify specific gaps, highlight strengths, and suggest concrete improvements.
Populate each field of the output schema.
"""
