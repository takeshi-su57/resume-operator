"""Generate PDF resumes using ReportLab."""

from pathlib import Path


def generate_pdf(sections: dict[str, str], output_path: Path) -> Path:
    """Generate a formatted resume PDF from optimized sections.

    Args:
        sections: Dict of section name to content (e.g., {"experience": "..."}).
        output_path: Where to write the PDF.

    Returns:
        Path to the generated PDF file.
    """
    # TODO: Use ReportLab to build a professionally formatted resume PDF
    # TODO: Support configurable templates/layouts in the future
    raise NotImplementedError
