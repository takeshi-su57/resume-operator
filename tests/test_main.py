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


class TestBootstrapCommand:
    def test_rejects_non_pdf(self, tmp_path: Path) -> None:
        fake = tmp_path / "resume.txt"
        fake.write_text("not a pdf")
        result = runner.invoke(app, ["bootstrap", "--resume", str(fake)])
        assert result.exit_code != 0
        assert "not a PDF" in _clean_output(result.output)

    @patch("resume_operator.main.build_graph")
    @patch("resume_operator.nodes.parse_resume.parse_resume")
    def test_calls_only_parse_resume_not_full_graph(
        self, mock_parse: MagicMock, mock_build: MagicMock, tmp_path: Path
    ) -> None:
        """Bootstrap must not invoke the full graph — that would burn LLM calls on
        ats_score / analyze_gaps / optimize_content the user never asked for."""
        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()
        out = tmp_path / "master.yaml"

        mock_parse.return_value = {
            "resume": ResumeData(
                name="Jane Smith",
                email="jane@example.com",
                experience=[
                    {
                        "role": "Engineer",
                        "company": "Corp",
                        "start_date": "2020",
                        "end_date": "present",
                        "description": "- Built APIs\n- Shipped to AWS",
                    }
                ],
                skills=["Python", "AWS"],
            ),
            "errors": [],
        }

        result = runner.invoke(app, ["bootstrap", "--resume", str(fake_pdf), "--output", str(out)])

        assert result.exit_code == 0, result.output
        mock_parse.assert_called_once()
        # Crucial: the full graph is not invoked during bootstrap.
        mock_build.assert_not_called()
        assert out.exists()

        import yaml

        written = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert written["name"] == "Jane Smith"
        # Bullets round-trip: dense newline description → list of ExperienceBullet entries.
        assert len(written["experience"][0]["bullets"]) == 2


class TestEnrichCommand:
    def _write_master_yaml(self, tmp_path: Path) -> Path:
        master = tmp_path / "master.yaml"
        master.write_text(
            "name: Jane Smith\n"
            "email: jane@example.com\n"
            "experience:\n"
            "  - id: exp-1\n"
            "    role: Senior Engineer\n"
            "    company: TechCorp\n"
            "    bullets:\n"
            "      - id: exp-1-b1\n"
            "        text: Led backend team\n"
            "skills: [Python]\n",
            encoding="utf-8",
        )
        return master

    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_dry_run_prints_questions_no_prompts(
        self, mock_get_llm: MagicMock, tmp_path: Path
    ) -> None:
        from resume_operator.tools.enrich import EnrichQuestionLLM, EnrichQuestionsLLMOutput

        master = self._write_master_yaml(tmp_path)
        facts = tmp_path / "facts.yaml"
        job = tmp_path / "job.txt"
        job.write_text("Backend engineer needed.", encoding="utf-8")

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = EnrichQuestionsLLMOutput(
            questions=[
                EnrichQuestionLLM(
                    area="role:exp-1",
                    question="How large was the backend team you led at TechCorp?",
                    why="JD asks for team leadership.",
                )
            ]
        )
        mock_get_llm.return_value = mock_llm

        result = runner.invoke(
            app,
            [
                "enrich",
                "--master",
                str(master),
                "--facts",
                str(facts),
                "--job",
                str(job),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "How large was the backend team" in result.output
        # Dry run must NOT write the facts bank.
        assert not facts.exists()

    def test_rejects_out_of_range_max_questions(self, tmp_path: Path) -> None:
        master = self._write_master_yaml(tmp_path)
        job = tmp_path / "job.txt"
        job.write_text("anything", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "enrich",
                "--master",
                str(master),
                "--job",
                str(job),
                "--max-questions",
                "99",
            ],
        )

        assert result.exit_code != 0
        assert "between 1 and 10" in _clean_output(result.output)

    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_full_session_writes_accepted_item(
        self, mock_get_llm: MagicMock, tmp_path: Path
    ) -> None:
        """One question asked; user answers; polish returns a project bullet;
        user accepts; facts_bank.yaml is written with the polished text."""
        from resume_operator.tools.enrich import (
            EnrichQuestionLLM,
            EnrichQuestionsLLMOutput,
            PolishedFactLLMOutput,
        )

        master = self._write_master_yaml(tmp_path)
        facts = tmp_path / "facts.yaml"
        job = tmp_path / "job.txt"
        job.write_text("Backend engineer needed.", encoding="utf-8")

        # Two distinct LLM calls during enrich: questions pass, then polish pass.
        # get_structured_llm returns a fresh mock each call; we stash distinct
        # return_values on each via side_effect.
        question_llm = MagicMock()
        question_llm.invoke.return_value = EnrichQuestionsLLMOutput(
            questions=[
                EnrichQuestionLLM(
                    question="Did you design any public APIs?",
                    why="JD emphasizes API design.",
                )
            ]
        )
        polish_llm = MagicMock()
        polish_llm.invoke.return_value = PolishedFactLLMOutput(
            polished_text="Designed RESTful API serving 50+ endpoints.",
            bucket="project",
        )
        mock_get_llm.side_effect = [question_llm, polish_llm]

        # stdin: answer → accept
        user_input = "I designed a REST API for our internal tools.\na\n"

        result = runner.invoke(
            app,
            [
                "enrich",
                "--master",
                str(master),
                "--facts",
                str(facts),
                "--job",
                str(job),
                "--max-questions",
                "1",
            ],
            input=user_input,
        )

        assert result.exit_code == 0, result.output
        assert facts.exists()

        import yaml

        written = yaml.safe_load(facts.read_text(encoding="utf-8"))
        assert len(written["projects"]) == 1
        assert "RESTful API" in written["projects"][0]["text"]
        assert written["projects"][0]["source"].startswith("enrich ")

    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_session_with_no_questions_exits_cleanly(
        self, mock_get_llm: MagicMock, tmp_path: Path
    ) -> None:
        from resume_operator.tools.enrich import EnrichQuestionsLLMOutput

        master = self._write_master_yaml(tmp_path)
        facts = tmp_path / "facts.yaml"
        job = tmp_path / "job.txt"
        job.write_text("anything", encoding="utf-8")

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = EnrichQuestionsLLMOutput(questions=[])
        mock_get_llm.return_value = mock_llm

        result = runner.invoke(
            app,
            ["enrich", "--master", str(master), "--facts", str(facts), "--job", str(job)],
        )

        assert result.exit_code == 0
        assert "No questions" in _clean_output(result.output)
        assert not facts.exists()


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
