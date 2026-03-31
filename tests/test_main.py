"""Tests for CLI commands in main.py."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from resume_operator.main import app
from resume_operator.state import (
    ATSScore,
    GapAnalysis,
    OptimizedResume,
    ResumeData,
)

runner = CliRunner()


def _clean_output(text: str) -> str:
    """Remove ANSI codes and Rich panel borders for reliable assertions."""
    # Strip ANSI escape codes
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    # Strip Rich box-drawing characters
    text = re.sub(r"[│╭╰╮╯─]", " ", text)
    # Collapse whitespace
    return re.sub(r"\s+", " ", text)


class TestParseResumeCommand:
    def test_file_not_found(self) -> None:
        """Nonexistent file path prints error."""
        result = runner.invoke(app, ["parse-resume", "--resume", "nonexistent.pdf"])

        assert result.exit_code != 0
        assert "does not exist" in _clean_output(result.output)

    def test_not_a_file(self, tmp_path: Path) -> None:
        """Directory path prints error."""
        result = runner.invoke(app, ["parse-resume", "--resume", str(tmp_path)])

        assert result.exit_code != 0
        assert "does not exist or is not a file" in _clean_output(result.output)

    def test_not_a_pdf(self, tmp_path: Path) -> None:
        """Non-PDF file is rejected."""
        fake_txt = tmp_path / "resume.txt"
        fake_txt.write_text("not a pdf")
        result = runner.invoke(app, ["parse-resume", "--resume", str(fake_txt)])

        assert result.exit_code != 0
        assert "not a PDF" in _clean_output(result.output)

    @patch("resume_operator.main.build_graph")
    def test_successful_parse(self, mock_build: MagicMock, tmp_path: Path) -> None:
        """Successful parse displays resume data."""
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "resume": ResumeData(
                name="Jane Smith",
                email="jane@example.com",
                phone="555-0100",
                skills=["Python", "AWS"],
                experience=[{"title": "Engineer", "company": "Corp"}],
                education=[{"degree": "BS", "institution": "State U"}],
                certifications=["AWS SAA"],
            ),
            "errors": [],
        }
        mock_build.return_value = mock_graph

        result = runner.invoke(app, ["parse-resume", "--resume", str(fake_pdf)])

        assert result.exit_code == 0
        assert "Jane Smith" in result.output
        assert "jane@example.com" in result.output
        assert "Python" in result.output
        assert "1 entries" in result.output

    @patch("resume_operator.main.build_graph")
    def test_pipeline_errors(self, mock_build: MagicMock, tmp_path: Path) -> None:
        """Pipeline errors are displayed in output and exit code is 1."""
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "resume": ResumeData(),
            "errors": ["PDF extraction failed: corrupted file"],
        }
        mock_build.return_value = mock_graph

        result = runner.invoke(app, ["parse-resume", "--resume", str(fake_pdf)])

        assert result.exit_code == 1
        assert "PDF extraction failed" in result.output

    def test_resume_option_required(self) -> None:
        """Missing --resume option shows error."""
        result = runner.invoke(app, ["parse-resume"])

        assert result.exit_code != 0
        assert "Missing" in result.output or "--resume" in result.output


class TestRunCommand:
    def test_file_not_found(self) -> None:
        result = runner.invoke(app, ["run", "--resume", "nope.pdf", "--job", "nope.txt"])
        assert result.exit_code != 0
        assert "does not exist" in _clean_output(result.output)

    def test_resume_not_pdf(self, tmp_path: Path) -> None:
        fake_txt = tmp_path / "resume.docx"
        fake_txt.touch()
        fake_job = tmp_path / "job.txt"
        fake_job.write_text("Engineer")
        result = runner.invoke(app, ["run", "--resume", str(fake_txt), "--job", str(fake_job)])
        assert result.exit_code != 0
        assert "not a PDF" in _clean_output(result.output)

    def test_dry_run(self, tmp_path: Path) -> None:
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()
        fake_job = tmp_path / "job.txt"
        fake_job.write_text("Engineer")
        result = runner.invoke(
            app,
            [
                "run",
                "--resume",
                str(fake_pdf),
                "--job",
                str(fake_job),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "resume.pdf" in result.output

    def test_dry_run_invalid_file(self) -> None:
        result = runner.invoke(
            app, ["run", "--resume", "nope.pdf", "--job", "nope.txt", "--dry-run"]
        )
        assert result.exit_code != 0
        assert "does not exist" in _clean_output(result.output)

    @patch("resume_operator.main.build_graph")
    def test_successful_run(self, mock_build: MagicMock, tmp_path: Path) -> None:
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()
        fake_job = tmp_path / "job.txt"
        fake_job.write_text("Backend Engineer")

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "resume": ResumeData(name="Jane Smith", skills=["Python"]),
            "ats_score": ATSScore(
                score=0.85,
                reasoning="Good match",
                keyword_matches=["Python"],
                keyword_gaps=["K8s"],
            ),
            "gap_analysis": GapAnalysis(
                strengths=["Python"], gaps=["K8s"], suggestions=["Add K8s"]
            ),
            "optimized_resume": OptimizedResume(
                sections={"summary": "Optimized"},
                changes_made=["Added K8s to skills"],
            ),
            "output_path": "data/optimized_resume.pdf",
            "report": {"timestamp": "2026-03-30"},
        }
        mock_build.return_value = mock_graph

        result = runner.invoke(app, ["run", "--resume", str(fake_pdf), "--job", str(fake_job)])

        assert result.exit_code == 0
        assert "85%" in result.output
        assert "Added K8s to skills" in result.output
        assert "data/optimized_resume.pdf" in result.output
        assert "Pipeline completed successfully" in result.output

    @patch("resume_operator.main.build_graph")
    def test_displays_errors(self, mock_build: MagicMock, tmp_path: Path) -> None:
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()
        fake_job = tmp_path / "job.txt"
        fake_job.write_text("Engineer")

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "resume": ResumeData(),
            "errors": ["ats_score: LLM call failed: timeout"],
        }
        mock_build.return_value = mock_graph

        result = runner.invoke(app, ["run", "--resume", str(fake_pdf), "--job", str(fake_job)])

        assert "LLM call failed" in result.output


class TestScoreCommand:
    def test_resume_not_found(self, tmp_path: Path) -> None:
        fake_job = tmp_path / "job.txt"
        fake_job.write_text("Engineer")
        result = runner.invoke(app, ["score", "--resume", "nope.pdf", "--job", str(fake_job)])
        assert result.exit_code != 0
        assert "does not exist" in _clean_output(result.output)

    def test_job_not_found(self, tmp_path: Path) -> None:
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()
        result = runner.invoke(app, ["score", "--resume", str(fake_pdf), "--job", "nope.txt"])
        assert result.exit_code != 0
        assert "does not exist" in _clean_output(result.output)

    @patch("resume_operator.main.build_score_graph")
    def test_successful_score(self, mock_build: MagicMock, tmp_path: Path) -> None:
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()
        fake_job = tmp_path / "job.txt"
        fake_job.write_text("Backend Engineer")

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "resume": ResumeData(name="Jane"),
            "ats_score": ATSScore(
                score=0.72,
                reasoning="Good Python match",
                keyword_matches=["Python"],
                keyword_gaps=["K8s"],
            ),
        }
        mock_build.return_value = mock_graph

        result = runner.invoke(app, ["score", "--resume", str(fake_pdf), "--job", str(fake_job)])

        assert result.exit_code == 0
        assert "72%" in result.output
        assert "Good Python match" in result.output
        assert "Python" in result.output
        assert "K8s" in result.output

    @patch("resume_operator.main.build_score_graph")
    def test_pipeline_errors(self, mock_build: MagicMock, tmp_path: Path) -> None:
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()
        fake_job = tmp_path / "job.txt"
        fake_job.write_text("Engineer")

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "errors": ["parse_resume: PDF extraction failed"],
        }
        mock_build.return_value = mock_graph

        result = runner.invoke(app, ["score", "--resume", str(fake_pdf), "--job", str(fake_job)])

        assert "PDF extraction failed" in result.output
