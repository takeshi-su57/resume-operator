"""Prompt template for resume PDF text parsing."""

PARSE_RESUME = """Extract structured data from the following resume text.

Resume text:
{resume_text}

Return ONLY valid JSON with these fields:
{{
    "name": "...",
    "email": "...",
    "phone": "...",
    "summary": "...",
    "experience": [{{"title": "...", "company": "...", "dates": "...", "description": "..."}}],
    "education": [{{"degree": "...", "institution": "...", "dates": "..."}}],
    "skills": ["..."],
    "certifications": ["..."]
}}"""
