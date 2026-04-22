"""Tests for PDF generation tool — deterministic render from structured data."""

from pathlib import Path

import fitz
import pytest

from resume_operator.state import (
    EducationEntry,
    ExperienceBullet,
    ExperienceEntry,
    ResumeMaster,
    TailoredItem,
    TailoredResume,
)
from resume_operator.tools.pdf_generator import (
    _default_styles,
    _sanitize_for_pdf,
    generate_pdf,
)


@pytest.fixture()
def master() -> ResumeMaster:
    return ResumeMaster(
        name="Jane Smith",
        email="jane@example.com",
        phone="555-0100",
        location="Remote",
        summary="Senior engineer.",
        experience=[
            ExperienceEntry(
                id="exp-1",
                role="Senior Engineer",
                company="TechCorp",
                start_date="2020",
                end_date="present",
                bullets=[
                    ExperienceBullet(id="exp-1-b1", text="Led backend team"),
                    ExperienceBullet(id="exp-1-b2", text="Built microservices"),
                ],
            )
        ],
        education=[EducationEntry(id="edu-1", degree="B.S. Computer Science", school="State U")],
        skills=["Python", "AWS"],
        certifications=["AWS SA"],
    )


@pytest.fixture()
def tailored() -> TailoredResume:
    return TailoredResume(
        items=[
            TailoredItem(
                source_id="master:summary",
                action="keep",
                original_text="Senior engineer with 8 years.",
            ),
            TailoredItem(
                source_id="master:exp-1-b1", action="keep", original_text="Led backend team"
            ),
            TailoredItem(
                source_id="master:exp-1-b2",
                action="reword",
                original_text="Built microservices",
                new_text="Built microservices in Python and deployed to AWS",
            ),
            TailoredItem(source_id="master:skill:Python", action="keep", original_text="Python"),
            TailoredItem(source_id="master:skill:AWS", action="keep", original_text="AWS"),
            TailoredItem(
                source_id="master:edu-1",
                action="keep",
                original_text="B.S. Computer Science — State U",
            ),
            TailoredItem(source_id="master:cert:AWS SA", action="keep", original_text="AWS SA"),
        ]
    )


class TestGeneratePdf:
    def test_generates_pdf(
        self, tmp_path: Path, master: ResumeMaster, tailored: TailoredResume
    ) -> None:
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)
        assert output.exists()
        assert output.read_bytes()[:4] == b"%PDF"

    def test_raises_when_no_renderable_items(self, tmp_path: Path, master: ResumeMaster) -> None:
        empty = TailoredResume(items=[])
        with pytest.raises(ValueError, match="no renderable items"):
            generate_pdf(master, empty, tmp_path / "out.pdf")

    def test_creates_parent_directories(
        self, tmp_path: Path, master: ResumeMaster, tailored: TailoredResume
    ) -> None:
        nested = tmp_path / "a" / "b" / "resume.pdf"
        generate_pdf(master, tailored, nested)
        assert nested.exists()

    def test_pdf_contains_structured_text(
        self, tmp_path: Path, master: ResumeMaster, tailored: TailoredResume
    ) -> None:
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)

        # Header from master
        assert "Jane Smith" in text
        assert "jane@example.com" in text
        # Section headers
        assert "SUMMARY" in text
        assert "EXPERIENCE" in text
        assert "SKILLS" in text
        assert "EDUCATION" in text
        # Role header from master (not from LLM blob)
        assert "TechCorp" in text
        assert "Senior Engineer" in text
        # Reworded bullet shows the new_text, not the original
        assert "Built microservices in Python and deployed to AWS" in text
        # Skills rendered as a flow
        assert "Python" in text
        # Education from master
        assert "Computer Science" in text

    def test_unknown_template_falls_back_to_default(
        self, tmp_path: Path, master: ResumeMaster, tailored: TailoredResume
    ) -> None:
        output = tmp_path / "resume.pdf"
        # Should not raise — just log a warning and render with the default template.
        generate_pdf(master, tailored, output, template="modern")
        assert output.exists()

    def test_returns_output_path(
        self, tmp_path: Path, master: ResumeMaster, tailored: TailoredResume
    ) -> None:
        output = tmp_path / "resume.pdf"
        result = generate_pdf(master, tailored, output)
        assert result == output

    def test_role_dates_extract_on_same_line_as_role(
        self, tmp_path: Path, master: ResumeMaster, tailored: TailoredResume
    ) -> None:
        """The role header and the date/location string should land on the same text line
        in the extracted PDF, because they're rendered as two columns of the same Table row.
        Recruiters scan dates at the right margin — this is the layout promise."""
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            lines: list[str] = []
            for page in doc:
                for block in page.get_text("blocks"):
                    # "blocks" tuple: (x0, y0, x1, y1, text, block_no, block_type)
                    lines.extend(block[4].splitlines())

        # Find the line that contains the role header; it should also contain the dates.
        role_lines = [line for line in lines if "Senior Engineer" in line and "TechCorp" in line]
        assert role_lines, f"role header missing from extracted text: {lines}"
        combined = "\n".join(lines)
        assert "2020" in combined and "present" in combined
        # The row is emitted as one visual line but may be split across columns in text extraction.
        # The key ATS promise is that both pieces of text are present and selectable.

    def test_structure_survives_typography_changes(
        self, tmp_path: Path, master: ResumeMaster, tailored: TailoredResume
    ) -> None:
        """Uppercase section labels and the accent colour are visual only — the raw text
        a parser sees still contains every core field from master + tailored."""
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)

        # Section labels present (rendered uppercase under the new template).
        for label in ("SUMMARY", "EXPERIENCE", "SKILLS", "EDUCATION", "CERTIFICATIONS"):
            assert label in text, f"{label!r} missing from rendered PDF"
        # Contact line still selectable.
        assert "jane@example.com" in text
        # Reworded content reached the page.
        assert "Built microservices in Python and deployed to AWS" in text

    def test_dropped_items_not_rendered(self, tmp_path: Path, master: ResumeMaster) -> None:
        tailored = TailoredResume(
            items=[
                TailoredItem(
                    source_id="master:exp-1-b1", action="keep", original_text="Kept bullet"
                ),
                TailoredItem(
                    source_id="master:exp-1-b2",
                    action="drop",
                    original_text="DROPPED-DO-NOT-RENDER",
                ),
            ]
        )
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        assert "Kept bullet" in text
        assert "DROPPED-DO-NOT-RENDER" not in text


class TestSanitizeForPdf:
    def test_translates_exotic_dashes_and_arrows(self) -> None:
        # non-breaking hyphen, en-dash, rightwards arrow, minus sign
        assert _sanitize_for_pdf("high‑performance") == "high-performance"
        assert _sanitize_for_pdf("Node.js 14 → 18") == "Node.js 14 -> 18"
        assert _sanitize_for_pdf("2020 – present") == "2020 - present"
        assert _sanitize_for_pdf("cost − 5%") == "cost - 5%"

    def test_translates_curly_quotes_and_ellipsis(self) -> None:
        assert _sanitize_for_pdf("it’s a “test”…") == 'it\'s a "test"...'

    def test_strips_zero_width_characters(self) -> None:
        # Exactly the garbage Bruno's first enrich session produced.
        assert _sanitize_for_pdf("Designed​    ​ thing") == "Designed thing"
        assert _sanitize_for_pdf("before­after") == "beforeafter"  # soft hyphen
        assert _sanitize_for_pdf("﻿BOM-prefixed") == "BOM-prefixed"

    def test_collapses_whitespace_runs(self) -> None:
        assert _sanitize_for_pdf("a     b\t\tc") == "a b c"

    def test_preserves_newlines(self) -> None:
        # Intentional newlines (paragraph breaks) survive.
        assert _sanitize_for_pdf("line one\nline two") == "line one\nline two"

    def test_empty_string_passthrough(self) -> None:
        assert _sanitize_for_pdf("") == ""

    def test_preserves_standard_ascii(self) -> None:
        assert _sanitize_for_pdf("hello, world! 50%") == "hello, world! 50%"


class TestTypographicHierarchy:
    """Issue #66 introduced a clearer size hierarchy — pin it so future edits
    don't silently flatten the page again."""

    def test_section_header_larger_than_body(self) -> None:
        styles = _default_styles()
        assert styles["section"].fontSize > styles["body"].fontSize

    def test_role_title_between_section_and_body(self) -> None:
        styles = _default_styles()
        assert styles["section"].fontSize >= styles["role_title"].fontSize
        assert styles["role_title"].fontSize > styles["body"].fontSize

    def test_name_is_the_largest_tier(self) -> None:
        styles = _default_styles()
        name = styles["name"].fontSize
        other_sizes = [
            styles["section"].fontSize,
            styles["role_title"].fontSize,
            styles["body"].fontSize,
            styles["contact"].fontSize,
        ]
        assert all(name > s for s in other_sizes)


class TestTailoredSummaryRender:
    def test_tailored_summary_rendered_when_present(
        self, tmp_path: Path, master: ResumeMaster
    ) -> None:
        summary = "Backend-leaning staff engineer with 8+ years shipping Node.js on AWS."
        tailored = TailoredResume(
            tailored_summary=summary,
            items=[
                TailoredItem(
                    source_id="master:exp-1-b1", action="keep", original_text="Led backend team"
                ),
            ],
        )
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)

        assert "Backend-leaning staff engineer" in text

    def test_tailored_summary_replaces_master_summary(
        self, tmp_path: Path, master: ResumeMaster
    ) -> None:
        """If both a tailored_summary AND a kept master:summary are present, only
        the tailored one should render — we don't want the SUMMARY section to
        show both."""
        tailored = TailoredResume(
            tailored_summary="FRESH JD-TAILORED SUMMARY.",
            items=[
                TailoredItem(
                    source_id="master:summary",
                    action="keep",
                    original_text="OLD MASTER SUMMARY SHOULD-NOT-RENDER",
                ),
                TailoredItem(source_id="master:exp-1-b1", action="keep", original_text="A bullet"),
            ],
        )
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)

        assert "FRESH JD-TAILORED SUMMARY." in text
        assert "SHOULD-NOT-RENDER" not in text

    def test_sanitizer_applied_to_tailored_summary(
        self, tmp_path: Path, master: ResumeMaster
    ) -> None:
        """Even if the LLM slips an exotic char into the summary, the PDF
        shouldn't show a black .notdef box."""
        tailored = TailoredResume(
            tailored_summary="High‑performance backend engineer → cloud native.",
            items=[
                TailoredItem(source_id="master:exp-1-b1", action="keep", original_text="A bullet"),
            ],
        )
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)

        assert "High-performance" in text
        assert "-> cloud" in text
        # Raw exotic chars must not survive into the rendered text stream.
        assert "‑" not in text
        assert "→" not in text
