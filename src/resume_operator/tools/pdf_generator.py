"""Generate PDF resumes using ReportLab."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def generate_pdf(sections: dict[str, str], output_path: Path) -> Path:
    """Generate a formatted resume PDF from optimized sections.

    Args:
        sections: Dict of section name to content (e.g., {"experience": "..."}).
        output_path: Where to write the PDF.

    Returns:
        Path to the generated PDF file.

    Raises:
        ValueError: If sections is empty.
    """
    if not sections:
        raise ValueError("sections must not be empty")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ResumeBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceBefore=2,
    )

    flowables: list[object] = []

    for i, (name, content) in enumerate(sections.items()):
        if i > 0:
            flowables.append(Spacer(1, 0.2 * inch))

        flowables.append(Paragraph(escape(name.title()), header_style))

        for paragraph_text in content.split("\n\n"):
            cleaned = paragraph_text.strip()
            if not cleaned:
                continue
            safe = escape(cleaned).replace("\n", "<br/>")
            flowables.append(Paragraph(safe, body_style))

    doc.build(flowables)
    return output_path
