"""Tests for the analyze_gaps node."""

from unittest.mock import MagicMock, patch

from resume_operator.nodes.analyze_gaps import analyze_gaps
from resume_operator.state import ResumeOptimizerState

VALID_LLM_JSON = """{
    "gaps": ["No Kubernetes experience", "Missing CI/CD pipeline knowledge"],
    "strengths": ["Strong Python skills", "AWS experience matches requirement"],
    "suggestions": ["Add Kubernetes certification", "Highlight any CI/CD exposure"]
}"""


class TestAnalyzeGaps:
    @patch("resume_operator.nodes.analyze_gaps.get_llm")
    def test_analyzes_gaps_successfully(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

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

    @patch("resume_operator.nodes.analyze_gaps.get_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        mock_get_llm.return_value = mock_llm

        result = analyze_gaps(sample_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "gap_analysis" not in result

    @patch("resume_operator.nodes.analyze_gaps.get_llm")
    def test_handles_invalid_json(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "not valid json"
        mock_get_llm.return_value = mock_llm

        result = analyze_gaps(sample_state)

        assert "errors" in result
        assert any("invalid JSON" in e for e in result["errors"])
        assert "gap_analysis" not in result

    @patch("resume_operator.nodes.analyze_gaps.get_llm")
    def test_handles_null_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        """LLM may return null for fields -- node should coerce to empty lists."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = """{
            "gaps": null,
            "strengths": null,
            "suggestions": null
        }"""
        mock_get_llm.return_value = mock_llm

        result = analyze_gaps(sample_state)

        assert "gap_analysis" in result
        assert result["gap_analysis"].gaps == []
        assert result["gap_analysis"].strengths == []
        assert result["gap_analysis"].suggestions == []

    @patch("resume_operator.nodes.analyze_gaps.get_llm")
    def test_returns_only_changed_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        result = analyze_gaps(sample_state)

        allowed_keys = {"gap_analysis", "errors"}
        assert set(result.keys()).issubset(allowed_keys)
        assert "resume" not in result
        assert "ats_score" not in result
