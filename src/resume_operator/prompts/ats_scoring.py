"""Prompt template for ATS compatibility scoring."""

ATS_SCORE = """Score how well this resume matches the job description for ATS compatibility.

Resume data:
{resume_json}

Job description:
{job_description}

Analyze keyword overlap, skills alignment, and experience relevance.

Return ONLY valid JSON:
{{
    "score": 0.0,
    "reasoning": "...",
    "keyword_matches": ["..."],
    "keyword_gaps": ["..."]
}}

Score range: 0.0 (no match) to 1.0 (perfect match)."""
