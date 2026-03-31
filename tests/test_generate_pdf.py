"""Tests for the generate_pdf node."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from resume_operator.nodes.generate_pdf import generate_pdf
from resume_operator.state import OptimizedResume, ResumeOptimizerState

SAMPLE_SECTIONS = {
    "summary": "Senior engineer with 8 years of Python experience.",
    "experience": "Led backend team building microservices.",
    "skills": "Python, AWS, Docker, Kubernetes",
}


def _mock_path(path_str: str, size: int = 12345) -> MagicMock:
    """Create a MagicMock that behaves like a Path return value."""
    mock = MagicMock(spec=Path)
    mock.stat.return_value.st_size = size
    mock.__str__ = lambda self: path_str
    return mock


class TestGeneratePdf:
    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    def test_calls_generator_and_returns_output_path(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.optimized_resume = OptimizedResume(sections=SAMPLE_SECTIONS)
        sample_state.output_path = "output/resume.pdf"
        mock_create_pdf.return_value = _mock_path("output/resume.pdf")

        result = generate_pdf(sample_state)

        mock_create_pdf.assert_called_once_with(SAMPLE_SECTIONS, Path("output/resume.pdf"))
        assert result["output_path"] == "output/resume.pdf"
        assert "errors" not in result

    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    def test_records_error_when_generator_fails(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.optimized_resume = OptimizedResume(sections=SAMPLE_SECTIONS)
        sample_state.output_path = "output/resume.pdf"
        mock_create_pdf.side_effect = ValueError("sections must not be empty")

        result = generate_pdf(sample_state)

        assert "errors" in result
        assert any("PDF generation failed" in e for e in result["errors"])
        assert "output_path" not in result

    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    def test_uses_default_path_when_output_path_empty(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.optimized_resume = OptimizedResume(sections=SAMPLE_SECTIONS)
        sample_state.output_path = ""
        mock_create_pdf.return_value = _mock_path("data/optimized_resume.pdf")

        result = generate_pdf(sample_state)

        mock_create_pdf.assert_called_once_with(SAMPLE_SECTIONS, Path("data/optimized_resume.pdf"))
        assert result["output_path"] == "data/optimized_resume.pdf"

    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    def test_returns_only_changed_fields(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.optimized_resume = OptimizedResume(sections=SAMPLE_SECTIONS)
        sample_state.output_path = "out.pdf"
        mock_create_pdf.return_value = _mock_path("out.pdf")

        result = generate_pdf(sample_state)

        allowed_keys = {"output_path", "errors"}
        assert set(result.keys()).issubset(allowed_keys)
        assert "optimized_resume" not in result
        assert "resume" not in result

    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    def test_preserves_existing_errors(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.optimized_resume = OptimizedResume(sections=SAMPLE_SECTIONS)
        sample_state.output_path = "out.pdf"
        sample_state.errors = ["previous error"]
        mock_create_pdf.side_effect = RuntimeError("disk full")

        result = generate_pdf(sample_state)

        assert "previous error" in result["errors"]
        assert any("PDF generation failed" in e for e in result["errors"])
        assert len(result["errors"]) == 2

    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    def test_no_errors_key_on_success(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.optimized_resume = OptimizedResume(sections=SAMPLE_SECTIONS)
        sample_state.output_path = "out.pdf"
        sample_state.errors = ["pre-existing error"]
        mock_create_pdf.return_value = _mock_path("out.pdf")

        result = generate_pdf(sample_state)

        assert "errors" not in result
