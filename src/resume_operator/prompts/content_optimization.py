"""Prompt template for resume content optimization."""

OPTIMIZE_CONTENT = """Optimize this resume to better match the job description.

Original resume data:
{resume_json}

Job description:
{job_description}

Gap analysis:
{gap_analysis}

Rewrite the resume sections to:
1. Incorporate missing keywords naturally
2. Emphasize relevant experience and skills
3. Improve ATS compatibility
4. Keep the original profile authentic — do not fabricate experience

Return ONLY valid JSON:
{{
    "sections": {{
        "summary": "optimized summary...",
        "experience": "optimized experience section...",
        "skills": "optimized skills section...",
        "education": "optimized education section..."
    }},
    "changes_made": ["description of change 1", "..."]
}}"""
