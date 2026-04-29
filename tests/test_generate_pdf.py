"""Tests for the generate_pdf node."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from lucky_resume.nodes.generate_pdf import generate_pdf
from lucky_resume.state import ResumeOptimizerState, TailoredItem, TailoredResume


def _tailored() -> TailoredResume:
    return TailoredResume(
        items=[
            TailoredItem(source_id="master:exp-1-b1", action="keep", original_text="Did stuff"),
        ]
    )


def _mock_path(path_str: str, size: int = 12345) -> MagicMock:
    """Create a MagicMock that behaves like a Path return value."""
    mock = MagicMock(spec=Path)
    mock.stat.return_value.st_size = size
    mock.__str__ = lambda self: path_str
    return mock


class TestGeneratePdf:
    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    def test_calls_generator_and_returns_output_path(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.tailored_resume = _tailored()
        sample_state.output_path = "output/resume.pdf"
        mock_create_pdf.return_value = _mock_path("output/resume.pdf")

        result = generate_pdf(sample_state)

        # New signature: master + tailored + output_path + template
        mock_create_pdf.assert_called_once()
        call_kwargs = mock_create_pdf.call_args.kwargs
        assert call_kwargs["master"] is sample_state.master
        assert call_kwargs["tailored"] is sample_state.tailored_resume
        assert call_kwargs["output_path"] == Path("output/resume.pdf")
        assert "template" in call_kwargs
        assert result["output_path"] == "output/resume.pdf"
        assert "errors" not in result

    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    def test_records_error_when_generator_fails(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.tailored_resume = _tailored()
        sample_state.output_path = "output/resume.pdf"
        mock_create_pdf.side_effect = ValueError("no renderable items")

        result = generate_pdf(sample_state)

        assert "errors" in result
        assert any("PDF generation failed" in e for e in result["errors"])
        assert "output_path" not in result

    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    def test_uses_default_path_when_output_path_empty(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.tailored_resume = _tailored()
        sample_state.output_path = ""
        mock_create_pdf.return_value = _mock_path("data/optimized_resume.pdf")

        result = generate_pdf(sample_state)

        call_kwargs = mock_create_pdf.call_args.kwargs
        assert call_kwargs["output_path"] == Path("data/optimized_resume.pdf")
        assert result["output_path"] == "data/optimized_resume.pdf"

    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    def test_returns_only_changed_fields(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.tailored_resume = _tailored()
        sample_state.output_path = "out.pdf"
        mock_create_pdf.return_value = _mock_path("out.pdf")

        result = generate_pdf(sample_state)

        allowed_keys = {"output_path", "errors"}
        assert set(result.keys()).issubset(allowed_keys)

    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    def test_preserves_existing_errors(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.tailored_resume = _tailored()
        sample_state.output_path = "out.pdf"
        sample_state.errors = ["previous error"]
        mock_create_pdf.side_effect = RuntimeError("disk full")

        result = generate_pdf(sample_state)

        assert "previous error" in result["errors"]
        assert any("PDF generation failed" in e for e in result["errors"])
        assert len(result["errors"]) == 2

    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    def test_no_errors_key_on_success(
        self, mock_create_pdf: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        sample_state.tailored_resume = _tailored()
        sample_state.output_path = "out.pdf"
        sample_state.errors = ["pre-existing error"]
        mock_create_pdf.return_value = _mock_path("out.pdf")

        result = generate_pdf(sample_state)

        assert "errors" not in result

    def test_empty_tailored_resume_skips(self, sample_state: ResumeOptimizerState) -> None:
        sample_state.tailored_resume = TailoredResume(items=[])
        result = generate_pdf(sample_state)

        assert "errors" in result
        assert any("no tailored items" in e for e in result["errors"])
        assert "output_path" not in result
