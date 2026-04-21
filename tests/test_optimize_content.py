"""Tests for the optimize_content node — per-item tailoring with fabrication guard."""

from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from resume_operator.nodes.optimize_content import (
    TailoredItemLLM,
    TailoredResumeLLMOutput,
    optimize_content,
)
from resume_operator.state import ResumeOptimizerState

VALID_OUTPUT = TailoredResumeLLMOutput(
    items=[
        TailoredItemLLM(source_id="master:summary", action="keep", original_text="summary text"),
        TailoredItemLLM(
            source_id="master:exp-1-b1",
            action="reword",
            original_text="Led backend team",
            new_text="Led backend team building Kubernetes-native microservices",
        ),
        TailoredItemLLM(
            source_id="master:exp-1-b2", action="keep", original_text="Built microservices"
        ),
        TailoredItemLLM(source_id="master:exp-2-b1", action="drop", original_text="Full-stack"),
        TailoredItemLLM(source_id="master:skill:Python", action="keep", original_text="Python"),
    ],
    notes=["Emphasized backend/microservices, dropped full-stack bullet."],
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


class TestOptimizeContent:
    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_builds_tailored_resume(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(VALID_OUTPUT)

        result = optimize_content(sample_state)

        assert "tailored_resume" in result
        assert len(result["tailored_resume"].items) == 5
        assert result["tailored_resume"].items[1].action == "reword"
        assert "Kubernetes-native" in result["tailored_resume"].items[1].new_text
        # Legacy projection still populates sections for back-compat.
        assert "optimized_resume" in result
        assert result["optimized_resume"].sections["experience"].startswith("- ")
        assert result["optimized_resume"].sections["skills"] == "Python"

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_rejects_fabricated_source_id(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            TailoredResumeLLMOutput(
                items=[
                    TailoredItemLLM(source_id="master:exp-1-b1", action="keep"),
                    # This ID does not exist in the source index — should be rejected.
                    TailoredItemLLM(source_id="master:exp-99-b99", action="keep"),
                ]
            )
        )

        result = optimize_content(sample_state)

        assert len(result["tailored_resume"].items) == 1
        assert any("fabricated source_id" in e for e in result["errors"])

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_coerces_unknown_action(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            TailoredResumeLLMOutput(
                items=[TailoredItemLLM(source_id="master:exp-1-b1", action="delete")]
            )
        )

        result = optimize_content(sample_state)

        # Unknown action coerced to the safe default "keep".
        assert result["tailored_resume"].items[0].action == "keep"

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API error"))

        result = optimize_content(sample_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "tailored_resume" not in result

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_handles_schema_validation_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        try:
            TailoredResumeLLMOutput.model_validate({"items": "not-a-list"})
        except ValidationError as exc:
            mock_get_llm.return_value = _make_llm(exc)

        result = optimize_content(sample_state)

        assert "errors" in result
        assert any("schema-invalid" in e for e in result["errors"])
        assert "tailored_resume" not in result

    def test_skips_when_master_is_empty(self) -> None:
        state = ResumeOptimizerState()  # empty master + facts
        result = optimize_content(state)

        assert "errors" in result
        assert any("source index is empty" in e for e in result["errors"])
