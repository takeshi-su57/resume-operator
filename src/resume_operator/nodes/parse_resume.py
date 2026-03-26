"""Node: Extract structured data from resume PDF."""

from resume_operator.state import ResumeOptimizerState


def parse_resume(state: ResumeOptimizerState) -> dict:
    """Parse resume PDF and extract structured data.

    Uses PyMuPDF to extract raw text, then LLM to structure it into
    ResumeData fields (name, experience, education, skills, etc.).
    """
    # TODO: Extract text via tools/pdf_parser.py
    # TODO: Send to LLM with prompts/resume_parsing.py template
    # TODO: Parse LLM JSON response into ResumeData fields
    return {}
