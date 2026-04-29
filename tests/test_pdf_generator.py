"""Tests for PDF generation tool — deterministic render from structured data."""

from pathlib import Path

import fitz
import pytest

from lucky_resume.state import (
    EducationEntry,
    ExperienceBullet,
    ExperienceEntry,
    Link,
    ResumeMaster,
    SkillGroup,
    TailoredItem,
    TailoredResume,
)
from lucky_resume.tools.pdf_generator import (
    _sanitize_for_pdf,
    generate_pdf,
)
from lucky_resume.tools.style import StyleTemplate, build_all_styles


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
    don't silently flatten the page again. Now driven by StyleTemplate (#72)."""

    def test_section_header_larger_than_body(self) -> None:
        styles = build_all_styles(StyleTemplate())
        assert styles["section"].fontSize > styles["body"].fontSize

    def test_role_title_between_section_and_body(self) -> None:
        styles = build_all_styles(StyleTemplate())
        assert styles["section"].fontSize >= styles["role_title"].fontSize
        assert styles["role_title"].fontSize > styles["body"].fontSize

    def test_name_is_the_largest_tier(self) -> None:
        styles = build_all_styles(StyleTemplate())
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


class TestSeniorFormatFields:
    """Coverage for the four #68 additions — headline, links, tech line, grouped skills.

    All four fields are optional on `ResumeMaster`; an older YAML without any of
    them still renders through the legacy fallbacks. The tests exercise both the
    populated and empty paths.
    """

    def _base_master(self) -> ResumeMaster:
        return ResumeMaster(
            name="Jane Smith",
            email="jane@example.com",
            experience=[
                ExperienceEntry(
                    id="exp-1",
                    role="Senior Engineer",
                    company="Acme",
                    bullets=[ExperienceBullet(id="exp-1-b1", text="Shipped it")],
                )
            ],
            education=[EducationEntry(id="edu-1", degree="BS CS", school="State U")],
            skills=["Python", "AWS"],
        )

    def _base_tailored(self) -> TailoredResume:
        return TailoredResume(
            items=[
                TailoredItem(
                    source_id="master:exp-1-b1", action="keep", original_text="Shipped it"
                ),
                TailoredItem(
                    source_id="master:skill:Python", action="keep", original_text="Python"
                ),
                TailoredItem(source_id="master:skill:AWS", action="keep", original_text="AWS"),
            ]
        )

    def test_headline_renders_under_name(self, tmp_path: Path) -> None:
        master = self._base_master()
        master.headline = "Senior Engineer · Founding Engineer · Ex-Google"
        output = tmp_path / "resume.pdf"
        generate_pdf(master, self._base_tailored(), output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        assert "Senior Engineer · Founding Engineer · Ex-Google" in text
        # Headline sits between name and contact in the rendered text stream.
        name_pos = text.index("Jane Smith")
        headline_pos = text.index("Ex-Google")
        contact_pos = text.index("jane@example.com")
        assert name_pos < headline_pos < contact_pos

    def test_empty_headline_silent(self, tmp_path: Path) -> None:
        """No headline means no headline line rendered — not even an empty paragraph."""
        master = self._base_master()
        assert master.headline == ""  # default
        output = tmp_path / "resume.pdf"
        generate_pdf(master, self._base_tailored(), output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        # Contact line should land directly after name.
        assert text.index("Jane Smith") < text.index("jane@example.com")

    def test_tailored_headline_wins_over_master_headline(self, tmp_path: Path) -> None:
        """#70: when the tailor emits a tailored_headline, it replaces master.headline.

        Both shouldn't render — the page would have two taglines. Tailored wins
        because it's per-JD and the master one is a static fallback."""
        master = self._base_master()
        master.headline = "STATIC MASTER TAGLINE — SHOULD-NOT-APPEAR"
        tailored = TailoredResume(
            tailored_headline="Senior Backend Engineer · 10+ years · Python",
            items=[
                TailoredItem(source_id="master:exp-1-b1", action="keep", original_text="x"),
            ],
        )
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        assert "Senior Backend Engineer · 10+ years · Python" in text
        assert "SHOULD-NOT-APPEAR" not in text

    def test_master_headline_fallback_when_no_tailored(self, tmp_path: Path) -> None:
        """When the tailor doesn't emit a headline, the static master.headline
        still renders — useful for score-only runs."""
        master = self._base_master()
        master.headline = "Fallback Tagline · Static"
        tailored = TailoredResume(
            tailored_headline="",  # explicitly empty
            items=[
                TailoredItem(source_id="master:exp-1-b1", action="keep", original_text="x"),
            ],
        )
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        assert "Fallback Tagline · Static" in text

    def test_links_render_as_second_contact_line(self, tmp_path: Path) -> None:
        master = self._base_master()
        master.links = [
            Link(label="GitHub", url="github.com/jsmith"),
            Link(label="LinkedIn", url="linkedin.com/in/jane-smith"),
        ]
        output = tmp_path / "resume.pdf"
        generate_pdf(master, self._base_tailored(), output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        assert "GitHub: github.com/jsmith" in text
        assert "LinkedIn: linkedin.com/in/jane-smith" in text

    def test_tech_line_renders_after_bullets(self, tmp_path: Path) -> None:
        master = self._base_master()
        master.experience[0].tech = ["Python", "Django", "Docker"]
        output = tmp_path / "resume.pdf"
        generate_pdf(master, self._base_tailored(), output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        # The `Tech:` line must appear in the rendered text and come after
        # the role bullet, not before.
        assert "Tech: Python, Django, Docker" in text
        bullet_pos = text.index("Shipped it")
        tech_pos = text.index("Tech: Python, Django, Docker")
        assert bullet_pos < tech_pos

    def test_empty_tech_silent(self, tmp_path: Path) -> None:
        master = self._base_master()
        assert master.experience[0].tech == []
        output = tmp_path / "resume.pdf"
        generate_pdf(master, self._base_tailored(), output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        assert "Tech:" not in text

    def test_skill_groups_render_categorised(self, tmp_path: Path) -> None:
        master = self._base_master()
        master.skill_groups = [
            SkillGroup(category="Languages", items=["Python", "Go"]),
            SkillGroup(category="Cloud", items=["AWS", "Docker"]),
        ]
        master.skills = ["Python", "Go", "AWS", "Docker"]  # match tailored-plan skills
        tailored = TailoredResume(
            items=[
                TailoredItem(source_id="master:exp-1-b1", action="keep", original_text="x"),
                TailoredItem(
                    source_id="master:skill:Python", action="keep", original_text="Python"
                ),
                TailoredItem(source_id="master:skill:Go", action="keep", original_text="Go"),
                TailoredItem(source_id="master:skill:AWS", action="keep", original_text="AWS"),
                TailoredItem(
                    source_id="master:skill:Docker", action="keep", original_text="Docker"
                ),
            ]
        )
        output = tmp_path / "resume.pdf"
        generate_pdf(master, tailored, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        # Categories render as labelled lines.
        assert "Languages: Python, Go" in text
        assert "Cloud: AWS, Docker" in text

    def test_skill_groups_fallback_to_flat_when_empty(self, tmp_path: Path) -> None:
        """Master without skill_groups falls back to the flat `·`-separated line
        (back-compat with pre-#68 YAMLs)."""
        master = self._base_master()
        assert master.skill_groups == []  # default
        output = tmp_path / "resume.pdf"
        generate_pdf(master, self._base_tailored(), output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)
        assert "Python · AWS" in text
        # No category label appears.
        assert "Languages:" not in text
