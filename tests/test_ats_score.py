"""Tests for the ats_score node."""

from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from resume_operator.nodes.ats_score import ATSScoreLLMOutput, ats_score
from resume_operator.state import ResumeOptimizerState


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


class TestAtsScore:
    @patch("resume_operator.nodes.ats_score.get_structured_llm")
    def test_scores_resume_successfully(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            ATSScoreLLMOutput(
                score=0.85,
                reasoning="Strong Python and AWS match, missing Kubernetes experience.",
                keyword_matches=["Python", "AWS", "microservices"],
                keyword_gaps=["Kubernetes", "CI/CD"],
            )
        )

        result = ats_score(sample_state)

        assert "ats_score" in result
        assert result["ats_score"].score == 0.85
        assert result["ats_score"].keyword_matches == ["Python", "AWS", "microservices"]
        assert result["ats_score"].keyword_gaps == ["Kubernetes", "CI/CD"]

    @patch("resume_operator.nodes.ats_score.get_structured_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API error"))

        result = ats_score(sample_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "ats_score" not in result

    @patch("resume_operator.nodes.ats_score.get_structured_llm")
    def test_handles_schema_validation_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        try:
            ATSScoreLLMOutput.model_validate({"score": "nope", "reasoning": "x"})
        except ValidationError as exc:
            mock_get_llm.return_value = _make_llm(exc)

        result = ats_score(sample_state)

        assert "errors" in result
        assert any("schema-invalid" in e for e in result["errors"])
        assert "ats_score" not in result

    @patch("resume_operator.nodes.ats_score.get_structured_llm")
    def test_clamps_score_above_one(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(ATSScoreLLMOutput(score=1.5, reasoning="x"))

        result = ats_score(sample_state)

        assert result["ats_score"].score == 1.0

    @patch("resume_operator.nodes.ats_score.get_structured_llm")
    def test_clamps_score_below_zero(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(ATSScoreLLMOutput(score=-0.5, reasoning="x"))

        result = ats_score(sample_state)

        assert result["ats_score"].score == 0.0

    @patch("resume_operator.nodes.ats_score.get_structured_llm")
    def test_returns_only_changed_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(ATSScoreLLMOutput(score=0.5, reasoning="x"))

        result = ats_score(sample_state)

        allowed_keys = {"ats_score", "errors"}
        assert set(result.keys()).issubset(allowed_keys)

    def test_empty_resume_data(self, sample_state: ResumeOptimizerState) -> None:
        """Skips scoring when resume data is empty."""
        sample_state.resume.raw_text = ""
        result = ats_score(sample_state)

        assert "errors" in result
        assert any("resume data is empty" in e for e in result["errors"])
        assert "ats_score" not in result
