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
from resume_operator.tools.pdf_generator import generate_pdf


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
