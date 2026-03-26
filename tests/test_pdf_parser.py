"""Tests for PDF text extraction tool."""

from pathlib import Path

import fitz
import pytest

from resume_operator.tools.pdf_parser import extract_text


def _create_pdf(path: Path, pages: list[str]) -> None:
    """Helper to create a PDF with given text on each page."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


class TestExtractText:
    def test_extracts_text_from_valid_pdf(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "resume.pdf"
        _create_pdf(pdf_path, ["Hello World"])
        result = extract_text(pdf_path)
        assert "Hello World" in result

    def test_extracts_text_from_multipage_pdf(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "multi.pdf"
        _create_pdf(pdf_path, ["Page one content", "Page two content"])
        result = extract_text(pdf_path)
        assert "Page one content" in result
        assert "Page two content" in result

    def test_raises_file_not_found_for_missing_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.pdf"
        with pytest.raises(FileNotFoundError, match="PDF file not found"):
            extract_text(missing)

    def test_raises_value_error_for_empty_pdf(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "empty.pdf"
        _create_pdf(pdf_path, [""])
        with pytest.raises(ValueError, match="No extractable text"):
            extract_text(pdf_path)
