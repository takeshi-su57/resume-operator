"""Tests for the ats_score node."""

from unittest.mock import MagicMock, patch

from resume_operator.nodes.ats_score import ats_score
from resume_operator.state import ResumeOptimizerState

VALID_LLM_JSON = """{
    "score": 0.85,
    "reasoning": "Strong Python and AWS match, missing Kubernetes experience.",
    "keyword_matches": ["Python", "AWS", "microservices"],
    "keyword_gaps": ["Kubernetes", "CI/CD"]
}"""


class TestAtsScore:
    @patch("resume_operator.nodes.ats_score.get_llm")
    def test_scores_resume_successfully(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        result = ats_score(sample_state)

        assert "ats_score" in result
        assert result["ats_score"].score == 0.85
        expected_reasoning = "Strong Python and AWS match, missing Kubernetes experience."
        assert result["ats_score"].reasoning == expected_reasoning
        assert result["ats_score"].keyword_matches == ["Python", "AWS", "microservices"]
        assert result["ats_score"].keyword_gaps == ["Kubernetes", "CI/CD"]

    @patch("resume_operator.nodes.ats_score.get_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        mock_get_llm.return_value = mock_llm

        result = ats_score(sample_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "ats_score" not in result

    @patch("resume_operator.nodes.ats_score.get_llm")
    def test_handles_invalid_json(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "not valid json at all"
        mock_get_llm.return_value = mock_llm

        result = ats_score(sample_state)

        assert "errors" in result
        assert any("invalid JSON" in e for e in result["errors"])
        assert "ats_score" not in result

    @patch("resume_operator.nodes.ats_score.get_llm")
    def test_clamps_score_above_one(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"score": 1.5, "reasoning": "x", "keyword_matches": [], "keyword_gaps": []}'
        )
        mock_get_llm.return_value = mock_llm

        result = ats_score(sample_state)

        assert result["ats_score"].score == 1.0

    @patch("resume_operator.nodes.ats_score.get_llm")
    def test_clamps_score_below_zero(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = (
            '{"score": -0.5, "reasoning": "x", "keyword_matches": [], "keyword_gaps": []}'
        )
        mock_get_llm.return_value = mock_llm

        result = ats_score(sample_state)

        assert result["ats_score"].score == 0.0

    @patch("resume_operator.nodes.ats_score.get_llm")
    def test_handles_null_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        """LLM may return null for optional fields — node should coerce to defaults."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = """{
            "score": 0.5,
            "reasoning": null,
            "keyword_matches": null,
            "keyword_gaps": null
        }"""
        mock_get_llm.return_value = mock_llm

        result = ats_score(sample_state)

        assert "ats_score" in result
        assert result["ats_score"].score == 0.5
        assert result["ats_score"].reasoning == ""
        assert result["ats_score"].keyword_matches == []
        assert result["ats_score"].keyword_gaps == []

    @patch("resume_operator.nodes.ats_score.get_llm")
    def test_returns_only_changed_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        result = ats_score(sample_state)

        allowed_keys = {"ats_score", "errors"}
        assert set(result.keys()).issubset(allowed_keys)
        assert "resume" not in result
        assert "resume_path" not in result

    def test_empty_resume_data(self, sample_state: ResumeOptimizerState) -> None:
        """Skips scoring when resume data is empty."""
        sample_state.resume.raw_text = ""
        result = ats_score(sample_state)

        assert "errors" in result
        assert any("resume data is empty" in e for e in result["errors"])
        assert "ats_score" not in result
