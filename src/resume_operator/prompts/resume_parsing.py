"""Prompt template for resume PDF text parsing."""

PARSE_RESUME = """Extract structured data from the following resume text.

Populate every field of the output schema. For experience, each entry should
have `role`, `company`, `start_date`, `end_date`, and `description` (a short
summary or bullet list). For education, each entry should have `degree`,
`school`, `start_date`, `end_date`. Leave unknown fields empty rather than
guessing.

Resume text:
{resume_text}
"""
