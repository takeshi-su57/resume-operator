"""Tests for the optimize_content node."""

from unittest.mock import MagicMock, patch

from resume_operator.nodes.optimize_content import optimize_content
from resume_operator.state import ResumeOptimizerState

VALID_LLM_JSON = """{
    "sections": {
        "summary": "Senior engineer with 8 years of Python and cloud experience.",
        "experience": "Led backend team building microservices in Python on AWS.",
        "skills": "Python, Django, AWS, Docker, PostgreSQL, Kubernetes, CI/CD",
        "education": "B.S. Computer Science, State University, 2012-2016"
    },
    "changes_made": [
        "Added Kubernetes to skills section",
        "Emphasized CI/CD experience in work history",
        "Incorporated microservices keywords in summary"
    ]
}"""


class TestOptimizeContent:
    @patch("resume_operator.nodes.optimize_content.get_llm")
    def test_optimizes_content_successfully(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        result = optimize_content(sample_state)

        assert "optimized_resume" in result
        assert result["optimized_resume"].sections["summary"].startswith("Senior engineer")
        assert len(result["optimized_resume"].changes_made) == 3
        assert "Kubernetes" in result["optimized_resume"].changes_made[0]

    @patch("resume_operator.nodes.optimize_content.get_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        mock_get_llm.return_value = mock_llm

        result = optimize_content(sample_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "optimized_resume" not in result

    @patch("resume_operator.nodes.optimize_content.get_llm")
    def test_handles_invalid_json(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "not valid json"
        mock_get_llm.return_value = mock_llm

        result = optimize_content(sample_state)

        assert "errors" in result
        assert any("invalid JSON" in e for e in result["errors"])
        assert "optimized_resume" not in result

    @patch("resume_operator.nodes.optimize_content.get_llm")
    def test_handles_null_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        """LLM may return null for fields -- node should coerce to defaults."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = """{
            "sections": null,
            "changes_made": null
        }"""
        mock_get_llm.return_value = mock_llm

        result = optimize_content(sample_state)

        assert "optimized_resume" in result
        assert result["optimized_resume"].sections == {}
        assert result["optimized_resume"].changes_made == []

    @patch("resume_operator.nodes.optimize_content.get_llm")
    def test_preserves_all_section_keys(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        result = optimize_content(sample_state)

        sections = result["optimized_resume"].sections
        assert "summary" in sections
        assert "experience" in sections
        assert "skills" in sections
        assert "education" in sections

    @patch("resume_operator.nodes.optimize_content.get_llm")
    def test_returns_only_changed_fields(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        result = optimize_content(sample_state)

        allowed_keys = {"optimized_resume", "errors"}
        assert set(result.keys()).issubset(allowed_keys)
        assert "resume" not in result
        assert "gap_analysis" not in result
