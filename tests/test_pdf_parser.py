"""Tests for PDF text extraction tool."""

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from resume_operator.tools.pdf_parser import extract_text


def _create_text_pdf(path: Path, pages: list[str]) -> None:
    """Create a PDF with given text on each page using ReportLab."""
    c = canvas.Canvas(str(path), pagesize=letter)
    for i, text in enumerate(pages):
        if i > 0:
            c.showPage()
        if text:
            c.drawString(72, letter[1] - 72, text)
    c.save()


def _create_image_only_pdf(path: Path) -> None:
    """Create a PDF with only a drawn shape (no extractable text)."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.rect(1 * inch, 1 * inch, 2 * inch, 2 * inch, fill=1)
    c.save()


@pytest.fixture()
def valid_pdf(tmp_path: Path) -> Path:
    """Generate a single-page PDF with known text."""
    pdf_path = tmp_path / "resume.pdf"
    _create_text_pdf(pdf_path, ["Hello World"])
    return pdf_path


@pytest.fixture()
def multipage_pdf(tmp_path: Path) -> Path:
    """Generate a multi-page PDF with known text on each page."""
    pdf_path = tmp_path / "multi.pdf"
    _create_text_pdf(pdf_path, ["Page one content", "Page two content"])
    return pdf_path


@pytest.fixture()
def image_only_pdf(tmp_path: Path) -> Path:
    """Generate a PDF with only graphics, no extractable text."""
    pdf_path = tmp_path / "image_only.pdf"
    _create_image_only_pdf(pdf_path)
    return pdf_path


class TestExtractText:
    def test_extracts_text_from_valid_pdf(self, valid_pdf: Path) -> None:
        result = extract_text(valid_pdf)
        assert "Hello World" in result

    def test_multipage_extraction(self, multipage_pdf: Path) -> None:
        result = extract_text(multipage_pdf)
        assert "Page one content" in result
        assert "Page two content" in result

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.pdf"
        with pytest.raises(FileNotFoundError, match="PDF file not found"):
            extract_text(missing)

    def test_raises_on_empty_text(self, image_only_pdf: Path) -> None:
        with pytest.raises(ValueError, match="No extractable text"):
            extract_text(image_only_pdf)
