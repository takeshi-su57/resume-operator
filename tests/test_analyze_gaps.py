"""Tests for the analyze_gaps node."""

from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from lucky_resume.nodes.analyze_gaps import GapAnalysisLLMOutput, analyze_gaps
from lucky_resume.state import ResumeOptimizerState


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


class TestAnalyzeGaps:
    @patch("lucky_resume.nodes.analyze_gaps.get_structured_llm")
    def test_analyzes_gaps_successfully(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            GapAnalysisLLMOutput(
                gaps=["No Kubernetes experience", "Missing CI/CD pipeline knowledge"],
                strengths=["Strong Python skills", "AWS experience matches requirement"],
                suggestions=["Add Kubernetes certification", "Highlight any CI/CD exposure"],
            )
        )

        result = analyze_gaps(sample_state)

        assert "gap_analysis" in result
        assert result["gap_analysis"].gaps == [
            "No Kubernetes experience",
            "Missing CI/CD pipeline knowledge",
        ]
        assert result["gap_analysis"].strengths == [
            "Strong Python skills",
            "AWS experience matches requirement",
        ]
        assert result["gap_analysis"].suggestions == [
            "Add Kubernetes certification",
            "Highlight any CI/CD exposure",
        ]

    @patch("lucky_resume.nodes.analyze_gaps.get_structured_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API error"))

        result = analyze_gaps(sample_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "gap_analysis" not in result

    @patch("lucky_resume.nodes.analyze_gaps.get_structured_llm")
    def test_handles_schema_validation_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        # Simulate what with_structured_output does when the provider returns
        # a response the schema can't validate — surfaces as pydantic.ValidationError.
        try:
            GapAnalysisLLMOutput.model_validate({"gaps": "not-a-list"})
        except ValidationError as exc:
            mock_get_llm.return_value = _make_llm(exc)

        result = analyze_gaps(sample_state)

        assert "errors" in result
        assert any("schema-invalid" in e for e in result["errors"])
        assert "gap_analysis" not in result

    @patch("lucky_resume.nodes.analyze_gaps.get_structured_llm")
    def test_handles_empty_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(GapAnalysisLLMOutput())

        result = analyze_gaps(sample_state)

        assert "gap_analysis" in result
        assert result["gap_analysis"].gaps == []
        assert result["gap_analysis"].strengths == []
        assert result["gap_analysis"].suggestions == []

    @patch("lucky_resume.nodes.analyze_gaps.get_structured_llm")
    def test_returns_only_changed_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(GapAnalysisLLMOutput(gaps=["x"]))

        result = analyze_gaps(sample_state)

        allowed_keys = {"gap_analysis", "errors"}
        assert set(result.keys()).issubset(allowed_keys)
