"""Tests for CLI commands in main.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from resume_operator.main import app
from resume_operator.state import ResumeData

runner = CliRunner()


class TestParseResumeCommand:
    def test_file_not_found(self) -> None:
        """Nonexistent file path prints error and exits 1."""
        result = runner.invoke(app, ["parse-resume", "--resume", "nonexistent.pdf"])

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_not_a_file(self, tmp_path: Path) -> None:
        """Directory path prints error and exits 1."""
        result = runner.invoke(app, ["parse-resume", "--resume", str(tmp_path)])

        assert result.exit_code == 1
        assert "does not exist or is not a file" in result.output

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
