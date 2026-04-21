"""Prompt template for resume content optimization."""

OPTIMIZE_CONTENT = """Optimize this resume to better match the job description.

Original resume data:
{resume_json}

Facts bank (items NOT currently on the resume but available to pull in):
{facts_json}

Job description:
{job_description}

Gap analysis:
{gap_analysis}

Rewrite the resume sections to:
1. Incorporate missing keywords naturally
2. Emphasize relevant experience and skills from the resume
3. Pull relevant items from the facts bank into the output ONLY when they
   strengthen the match for this JD (mention which facts you used in
   `changes_made`)
4. Improve ATS compatibility
5. Keep the original profile authentic — never invent experience; only use
   what is in the resume data or the facts bank

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
