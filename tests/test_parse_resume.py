"""Tests for the parse_resume node."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from resume_operator.nodes.parse_resume import ResumeLLMOutput, parse_resume
from resume_operator.state import ResumeOptimizerState

SAMPLE_RESUME_TEXT = "Jane Smith\njane@example.com\nSenior Engineer at TechCorp"

VALID_OUTPUT = ResumeLLMOutput.model_validate(
    {
        "name": "Jane Smith",
        "email": "jane@example.com",
        "phone": "555-0100",
        "summary": "Senior software engineer",
        "experience": [
            {
                "role": "Senior Engineer",
                "company": "TechCorp",
                "start_date": "2020",
                "end_date": "present",
                "description": "Led backend team",
            }
        ],
        "education": [
            {
                "degree": "B.S. CS",
                "school": "State U",
                "start_date": "2012",
                "end_date": "2016",
            }
        ],
        "skills": ["Python", "AWS"],
        "certifications": ["AWS SA"],
    }
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


@pytest.fixture
def base_state() -> ResumeOptimizerState:
    return ResumeOptimizerState(
        resume_path="resume.pdf",
        job_description_text="Backend Engineer at BigCo. Requires Python.",
    )


class TestParseResume:
    @patch("resume_operator.nodes.parse_resume.get_structured_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_parses_resume_successfully(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_get_llm.return_value = _make_llm(VALID_OUTPUT)

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

    @patch("resume_operator.nodes.parse_resume.get_structured_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_records_error_on_llm_failure(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_get_llm.return_value = _make_llm(RuntimeError("API error"))

        result = parse_resume(base_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "resume" not in result

    @patch("resume_operator.nodes.parse_resume.get_structured_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_records_error_on_schema_mismatch(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        try:
            ResumeLLMOutput.model_validate({"experience": "not-a-list"})
        except ValidationError as exc:
            mock_get_llm.return_value = _make_llm(exc)

        result = parse_resume(base_state)

        assert "errors" in result
        assert any("schema-invalid" in e for e in result["errors"])
        assert "resume" not in result

    @patch("resume_operator.nodes.parse_resume.get_structured_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_returns_only_changed_fields(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock, base_state: ResumeOptimizerState
    ) -> None:
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_get_llm.return_value = _make_llm(VALID_OUTPUT)

        result = parse_resume(base_state)

        allowed_keys = {"resume", "master", "job_description", "errors"}
        assert set(result.keys()).issubset(allowed_keys)

    @patch("resume_operator.nodes.parse_resume.get_structured_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_reads_job_description_from_file(
        self, mock_extract: MagicMock, mock_get_llm: MagicMock
    ) -> None:
        state = ResumeOptimizerState(resume_path="resume.pdf", job_description_path="job.txt")
        mock_extract.return_value = SAMPLE_RESUME_TEXT
        mock_get_llm.return_value = _make_llm(VALID_OUTPUT)

        with patch("resume_operator.nodes.parse_resume.Path.read_text") as mock_read:
            mock_read.return_value = "Backend Engineer role"
            result = parse_resume(state)

        assert result["job_description"].raw_text == "Backend Engineer role"

    def test_empty_resume_path(self) -> None:
        state = ResumeOptimizerState(resume_path="")
        result = parse_resume(state)

        assert "errors" in result
        assert any("resume_path is empty" in e for e in result["errors"])
