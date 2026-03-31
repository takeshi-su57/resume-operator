"""Tests for the parse_resume node."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resume_operator.nodes.parse_resume import parse_resume
from resume_operator.state import ResumeOptimizerState

SAMPLE_RESUME_TEXT = "Jane Smith\njane@example.com\nSenior Engineer at TechCorp"

VALID_LLM_JSON = """{
    "name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "555-0100",
    "summary": "Senior software engineer",
    "experience": [
        {
            "title": "Senior Engineer",
            "company": "TechCorp",
            "dates": "2020-present",
            "description": "Led backend team"
        }
    ],
    "education": [
        {"degree": "B.S. CS", "institution": "State U", "dates": "2012-2016"}
    ],
    "skills": ["Python", "AWS"],
    "certifications": ["AWS SA"]
}"""


@pytest.fixture
def base_state() -> ResumeOptimizerState:
    return ResumeOptimizerState(
        resume_path="resume.pdf",
        job_description_text="Backend Engineer at BigCo. Requires Python.",
    )


class TestParseResume:
    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_parses_resume_successfully(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        result = parse_resume(base_state)

        assert "resume" in result
        assert result["resume"].name == "Jane Smith"
        assert result["resume"].email == "jane@example.com"
        assert result["resume"].skills == ["Python", "AWS"]
        assert result["resume"].raw_text == SAMPLE_RESUME_TEXT
        assert "job_description" in result
        assert result["job_description"].raw_text == base_state.job_description_text
        mock_extract.assert_called_once_with(Path("resume.pdf"))

    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_records_error_on_pdf_failure(
        self, mock_extract: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.side_effect = FileNotFoundError("PDF file not found: resume.pdf")

        result = parse_resume(base_state)

        assert "errors" in result
        assert any("PDF extraction failed" in e for e in result["errors"])
        assert "resume" not in result

    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_records_error_on_llm_failure(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        mock_get_llm.return_value = mock_llm

        result = parse_resume(base_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "resume" not in result

    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_records_error_on_invalid_json(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "not valid json at all"
        mock_get_llm.return_value = mock_llm

        result = parse_resume(base_state)

        assert "errors" in result
        assert any("invalid JSON" in e for e in result["errors"])
        assert "resume" not in result

    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_returns_only_changed_fields(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        result = parse_resume(base_state)

        # Should only contain resume and job_description, not the full state
        allowed_keys = {"resume", "job_description", "errors"}
        assert set(result.keys()).issubset(allowed_keys)
        assert "resume_path" not in result
        assert "ats_score" not in result

    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_reads_job_description_from_file(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock
    ) -> None:
        state = ResumeOptimizerState(
            resume_path="resume.pdf",
            job_description_path="job.txt",
        )
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_get_llm.return_value = mock_llm

        with patch("resume_operator.nodes.parse_resume.Path.read_text") as mock_read:
            mock_read.return_value = "Backend Engineer role"
            result = parse_resume(state)

        assert result["job_description"].raw_text == "Backend Engineer role"

    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_handles_null_fields_from_llm(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        """LLM may return null for optional fields — node should coerce to defaults."""
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = """{
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": null,
            "summary": null,
            "experience": null,
            "education": [],
            "skills": ["Python"],
            "certifications": null
        }"""
        mock_get_llm.return_value = mock_llm

        result = parse_resume(base_state)

        assert "resume" in result
        assert result["resume"].phone == ""
        assert result["resume"].summary == ""
        assert result["resume"].experience == []
        assert result["resume"].certifications == []
        assert result["resume"].skills == ["Python"]

    def test_empty_resume_path(self) -> None:
        """Empty resume_path returns error without processing."""
        state = ResumeOptimizerState(resume_path="")
        result = parse_resume(state)

        assert "errors" in result
        assert any("resume_path is empty" in e for e in result["errors"])
