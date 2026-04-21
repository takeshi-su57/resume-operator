"""Tests for the optimize_content node."""

from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from resume_operator.nodes.optimize_content import (
    OptimizedResumeLLMOutput,
    OptimizedSections,
    optimize_content,
)
from resume_operator.state import ResumeOptimizerState

VALID_OUTPUT = OptimizedResumeLLMOutput(
    sections=OptimizedSections(
        summary="Senior engineer with 8 years of Python and cloud experience.",
        experience="Led backend team building microservices in Python on AWS.",
        skills="Python, Django, AWS, Docker, PostgreSQL, Kubernetes, CI/CD",
        education="B.S. Computer Science, State University, 2012-2016",
    ),
    changes_made=[
        "Added Kubernetes to skills section",
        "Emphasized CI/CD experience in work history",
        "Incorporated microservices keywords in summary",
    ],
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
    def test_optimizes_content_successfully(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(VALID_OUTPUT)

        result = optimize_content(sample_state)

        assert "optimized_resume" in result
        assert result["optimized_resume"].sections["summary"].startswith("Senior engineer")
        assert len(result["optimized_resume"].changes_made) == 3
        assert "Kubernetes" in result["optimized_resume"].changes_made[0]

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API error"))

        result = optimize_content(sample_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "optimized_resume" not in result

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_handles_schema_validation_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        try:
            OptimizedResumeLLMOutput.model_validate({"changes_made": "not-a-list"})
        except ValidationError as exc:
            mock_get_llm.return_value = _make_llm(exc)

        result = optimize_content(sample_state)

        assert "errors" in result
        assert any("schema-invalid" in e for e in result["errors"])
        assert "optimized_resume" not in result

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_handles_empty_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(OptimizedResumeLLMOutput())

        result = optimize_content(sample_state)

        assert "optimized_resume" in result
        # Empty OptimizedSections dumps to {"summary": "", "experience": "", ...}
        assert set(result["optimized_resume"].sections.keys()) == {
            "summary",
            "experience",
            "skills",
            "education",
        }
        assert all(v == "" for v in result["optimized_resume"].sections.values())
        assert result["optimized_resume"].changes_made == []

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_preserves_all_section_keys(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(VALID_OUTPUT)

        result = optimize_content(sample_state)

        sections = result["optimized_resume"].sections
        assert "summary" in sections
        assert "experience" in sections
        assert "skills" in sections
        assert "education" in sections

    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    def test_returns_only_changed_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(VALID_OUTPUT)

        result = optimize_content(sample_state)

        allowed_keys = {"optimized_resume", "errors"}
        assert set(result.keys()).issubset(allowed_keys)
