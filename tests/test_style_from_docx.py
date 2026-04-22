"""Tests for `tools.style_from_docx`."""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from resume_operator.tools.style_from_docx import (
    StyleExtractionError,
    extract_style_from_docx,
)


def _build_minimal_docx(path: Path) -> None:
    """Build a tiny .docx with a recognisable set of styles so the extractor
    has something to work with. Avoids depending on a checked-in binary fixture.
    """
    doc = Document()
    # Set margins we can assert against.
    from docx.shared import Inches

    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

    # Default "Normal" style font: use a distinctive name we can check for.
    from docx.shared import Pt, RGBColor

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    # Heading 2 — used for section labels.
    h2 = doc.styles["Heading 2"]
    h2.font.size = Pt(16)
    h2.font.color.rgb = RGBColor(0x0F, 0x47, 0x61)

    doc.add_paragraph("My Name", style="Heading 1")
    doc.add_paragraph("SUMMARY", style="Heading 2")
    doc.add_paragraph("Body text goes here.")
    doc.save(str(path))


class TestExtractStyle:
    def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(StyleExtractionError, match="not found"):
            extract_style_from_docx(tmp_path / "nope.docx")

    def test_raises_on_non_docx(self, tmp_path: Path) -> None:
        bad = tmp_path / "not_really.docx"
        bad.write_bytes(b"this is not a zip file")
        with pytest.raises(StyleExtractionError):
            extract_style_from_docx(bad)

    def test_extracts_font_family_margins_colors(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "tiny.docx"
        _build_minimal_docx(docx_path)

        template = extract_style_from_docx(docx_path)

        # Font family came through from the Normal style.
        assert template.font_family == "Calibri"
        # Margins were read from the section config.
        assert template.margins.top == pytest.approx(0.75)
        assert template.margins.side == pytest.approx(0.5)
        # Accent colour picked up from the Heading 2 color.
        assert template.colors.accent.upper() == "#0F4761"
        # Template name derives from the source filename (stem).
        assert template.name == "tiny"

    def test_extracts_section_size_from_heading_2(self, tmp_path: Path) -> None:
        docx_path = tmp_path / "tiny.docx"
        _build_minimal_docx(docx_path)
        template = extract_style_from_docx(docx_path)
        # Heading 2 in our fixture has size 16pt.
        assert template.section.size == pytest.approx(16)
        # Name style falls back to the StyleTemplate default since this fixture
        # doesn't set a "Heading" or "Title" style explicitly.
        # (Just verify the field is positive — actual value depends on whatever
        # Word's default Heading 1 size ends up being in python-docx.)
        assert template.name_style.size > 0

    def test_andy_cv_real_world(self) -> None:
        """If Bruno's andy-wang-cv fixture is present locally, exercise the
        extractor against it. Skipped in CI where the .docx isn't checked in."""
        andy = Path("input/andy-wang-cv - Copy.docx")
        if not andy.exists():
            pytest.skip("Andy Wang .docx not present — local fixture only")

        template = extract_style_from_docx(andy)
        # Andy's CV uses the Aptos family.
        assert template.font_family.startswith("Aptos")
        # The document uses a deep blue accent — #0F4761.
        assert template.colors.accent.upper() == "#0F4761"
        # Margins in the sample are 0.5 inches all around.
        assert template.margins.top == pytest.approx(0.5)
        assert template.margins.side == pytest.approx(0.5)
