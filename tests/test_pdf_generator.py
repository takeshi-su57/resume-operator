"""Tests for PDF generation tool."""

from pathlib import Path

import fitz
import pytest

from resume_operator.tools.pdf_generator import generate_pdf


@pytest.fixture()
def sample_sections() -> dict[str, str]:
    """Sample resume sections for testing."""
    return {
        "summary": "Senior software engineer with 8 years of experience.",
        "experience": (
            "Senior Engineer at TechCorp\n2020-present\n\n"
            "Built microservices in Python and deployed to AWS."
        ),
        "skills": "Python, Django, AWS, Docker",
        "education": "B.S. Computer Science\nState University, 2012-2016",
    }


class TestGeneratePdf:
    def test_generates_pdf_from_sections(
        self, tmp_path: Path, sample_sections: dict[str, str]
    ) -> None:
        output = tmp_path / "resume.pdf"
        generate_pdf(sample_sections, output)

        assert output.exists()
        assert output.read_bytes()[:4] == b"%PDF"

    def test_raises_on_empty_sections(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="sections must not be empty"):
            generate_pdf({}, tmp_path / "out.pdf")

    def test_creates_parent_directories(
        self, tmp_path: Path, sample_sections: dict[str, str]
    ) -> None:
        nested = tmp_path / "a" / "b" / "resume.pdf"
        assert not nested.parent.exists()

        generate_pdf(sample_sections, nested)
        assert nested.exists()

    def test_pdf_contains_section_text(
        self, tmp_path: Path, sample_sections: dict[str, str]
    ) -> None:
        output = tmp_path / "resume.pdf"
        generate_pdf(sample_sections, output)

        with fitz.open(output) as doc:
            text = "\n".join(page.get_text() for page in doc)

        assert "Summary" in text
        assert "Experience" in text
        assert "Skills" in text
        assert "Education" in text
        assert "Senior software engineer" in text
        assert "TechCorp" in text
        assert "Python" in text
        assert "Computer Science" in text

    def test_returns_output_path(self, tmp_path: Path, sample_sections: dict[str, str]) -> None:
        output = tmp_path / "resume.pdf"
        result = generate_pdf(sample_sections, output)
        assert result == output
