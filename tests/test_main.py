"""Tests for CLI commands in main.py."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
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
        from resume_operator.state import (
            ExperienceBullet,
            ExperienceEntry,
            ResumeMaster,
        )

        fake_pdf = tmp_path / "resume.pdf"
        fake_pdf.touch()
        out = tmp_path / "master.yaml"

        mock_parse.return_value = {
            "resume": ResumeData(
                name="Jane Smith",
                email="jane@example.com",
                skills=["Python", "AWS"],
            ),
            "master": ResumeMaster(
                name="Jane Smith",
                email="jane@example.com",
                experience=[
                    ExperienceEntry(
                        id="exp-1",
                        role="Engineer",
                        company="Corp",
                        start_date="2020",
                        end_date="present",
                        bullets=[
                            ExperienceBullet(id="exp-1-b1", text="Built APIs"),
                            ExperienceBullet(id="exp-1-b2", text="Shipped to AWS"),
                        ],
                    )
                ],
                skills=["Python", "AWS"],
            ),
            "errors": [],
        }

        # `--no-interview` keeps the command headless so the test doesn't block on prompts.
        result = runner.invoke(
            app,
            ["bootstrap", "--resume", str(fake_pdf), "--output", str(out), "--no-interview"],
        )

        assert result.exit_code == 0, result.output
        mock_parse.assert_called_once()
        # Crucial: the full graph is not invoked during bootstrap.
        mock_build.assert_not_called()
        assert out.exists()

        import yaml

        written = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert written["name"] == "Jane Smith"
        # The master carries the ExperienceEntry's stable-ID bullets straight
        # through to the YAML — no round-trip through ResumeData's dict shape.
        assert len(written["experience"][0]["bullets"]) == 2


class TestEnrichCommandRemoved:
    """The standalone `enrich` command was folded into `run` (issue #64)."""

    def test_enrich_command_no_longer_exists(self) -> None:
        result = runner.invoke(app, ["enrich", "--help"])
        # Typer's "no such command" exit code is 2.
        assert result.exit_code != 0


class TestRunAutoEnrich:
    """Auto-enrich logic inside `run`. The trigger conditions are unit-tested
    against `_should_offer_enrich` directly so we don't have to mock stdin
    and TTY status for each scenario."""

    def _state(self, *, kept_count: int, optimization_skipped: bool = False) -> dict:
        from resume_operator.state import TailoredItem, TailoredResume

        items = [
            TailoredItem(source_id=f"master:exp-1-b{i}", action="keep") for i in range(kept_count)
        ]
        return {
            "tailored_resume": TailoredResume(items=items),
            "report": {"optimization_skipped": optimization_skipped},
        }

    @patch("sys.stdin.isatty", return_value=True)
    def test_offers_enrich_when_thin(self, _mock_tty: MagicMock, tmp_path: Path) -> None:
        from resume_operator.main import _should_offer_enrich

        master = tmp_path / "m.yaml"
        master.touch()
        # Threshold defaults to 6; 3 items is thin.
        assert (
            _should_offer_enrich(self._state(kept_count=3), no_enrich=False, master_path=master)
            is True
        )

    @patch("sys.stdin.isatty", return_value=True)
    def test_does_not_offer_when_full(self, _mock_tty: MagicMock, tmp_path: Path) -> None:
        from resume_operator.main import _should_offer_enrich

        master = tmp_path / "m.yaml"
        master.touch()
        # 10 items is well above default threshold of 6.
        assert (
            _should_offer_enrich(self._state(kept_count=10), no_enrich=False, master_path=master)
            is False
        )

    @patch("sys.stdin.isatty", return_value=True)
    def test_respects_no_enrich_flag(self, _mock_tty: MagicMock, tmp_path: Path) -> None:
        from resume_operator.main import _should_offer_enrich

        master = tmp_path / "m.yaml"
        master.touch()
        assert (
            _should_offer_enrich(self._state(kept_count=2), no_enrich=True, master_path=master)
            is False
        )

    @patch("sys.stdin.isatty", return_value=True)
    def test_skips_when_optimization_was_skipped(
        self, _mock_tty: MagicMock, tmp_path: Path
    ) -> None:
        """If ATS was high enough that optimize_content didn't run, we have no
        signal that the master is thin — skip the enrich offer."""
        from resume_operator.main import _should_offer_enrich

        master = tmp_path / "m.yaml"
        master.touch()
        state = self._state(kept_count=0, optimization_skipped=True)
        assert _should_offer_enrich(state, no_enrich=False, master_path=master) is False

    @patch("sys.stdin.isatty", return_value=False)
    def test_skips_when_no_tty(self, _mock_tty: MagicMock, tmp_path: Path) -> None:
        """Headless / scripted runs (CI, piped stdin) must never block on prompts."""
        from resume_operator.main import _should_offer_enrich

        master = tmp_path / "m.yaml"
        master.touch()
        assert (
            _should_offer_enrich(self._state(kept_count=2), no_enrich=False, master_path=master)
            is False
        )

    def test_skips_legacy_pdf_path(self, tmp_path: Path) -> None:
        """The legacy --resume PDF path doesn't surface a master object the
        enrich loop can use; skip the offer regardless of stdin/TTY."""
        from resume_operator.main import _should_offer_enrich

        assert (
            _should_offer_enrich(self._state(kept_count=2), no_enrich=False, master_path=None)
            is False
        )


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


class TestExtractStyleCommand:
    def test_rejects_non_docx(self, tmp_path: Path) -> None:
        not_docx = tmp_path / "resume.pdf"
        not_docx.touch()
        result = runner.invoke(
            app,
            [
                "extract-style",
                "--from",
                str(not_docx),
                "--output",
                str(tmp_path / "out.yaml"),
            ],
        )
        assert result.exit_code != 0
        assert "not a .docx" in _clean_output(result.output)

    def test_rejects_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "extract-style",
                "--from",
                str(tmp_path / "nope.docx"),
                "--output",
                str(tmp_path / "out.yaml"),
            ],
        )
        assert result.exit_code != 0
        assert "does not exist" in _clean_output(result.output)

    def test_extract_writes_yaml(self, tmp_path: Path) -> None:
        """End-to-end: build a tiny .docx, run extract-style, verify YAML."""
        from docx import Document as DocxDocument
        from docx.shared import Inches, Pt, RGBColor

        src = tmp_path / "ref.docx"
        doc = DocxDocument()
        for sec in doc.sections:
            sec.top_margin = Inches(0.4)
            sec.left_margin = Inches(0.4)
        normal = doc.styles["Normal"]
        normal.font.name = "Aptos"
        normal.font.size = Pt(11)
        h2 = doc.styles["Heading 2"]
        h2.font.size = Pt(15)
        h2.font.color.rgb = RGBColor(0x0F, 0x47, 0x61)
        doc.add_paragraph("SUMMARY", style="Heading 2")
        doc.save(str(src))

        out = tmp_path / "out.yaml"
        result = runner.invoke(app, ["extract-style", "--from", str(src), "--output", str(out)])

        assert result.exit_code == 0, result.output
        assert out.exists()

        import yaml

        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert data["font_family"] == "Aptos"
        assert data["margins"]["top"] == pytest.approx(0.4)
        assert data["colors"]["accent"].upper() == "#0F4761"
        assert data["section"]["size"] == pytest.approx(15)


class TestRunStyleFlag:
    @patch("resume_operator.main.build_graph")
    def test_style_flag_plumbed_into_initial_state(
        self, mock_build: MagicMock, tmp_path: Path
    ) -> None:
        """`run --style PATH` should put the style path into the graph's initial state
        so `generate_pdf` can pick it up."""
        master = tmp_path / "m.yaml"
        master.write_text("name: x\n", encoding="utf-8")
        job = tmp_path / "j.txt"
        job.write_text("jd", encoding="utf-8")
        style = tmp_path / "style.yaml"
        style.write_text("name: mine\n", encoding="utf-8")

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"errors": []}
        mock_build.return_value = mock_graph

        runner.invoke(
            app,
            [
                "run",
                "--master",
                str(master),
                "--job",
                str(job),
                "--style",
                str(style),
                "--no-enrich",
            ],
        )

        # First call to graph.invoke — inspect the kwargs dict.
        assert mock_graph.invoke.called
        initial = mock_graph.invoke.call_args.args[0]
        assert initial.get("style_path") == str(style)

    @patch("resume_operator.main.build_graph")
    def test_style_flag_rejects_missing_file(self, mock_build: MagicMock, tmp_path: Path) -> None:
        master = tmp_path / "m.yaml"
        master.write_text("name: x\n", encoding="utf-8")
        job = tmp_path / "j.txt"
        job.write_text("jd", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "run",
                "--master",
                str(master),
                "--job",
                str(job),
                "--style",
                str(tmp_path / "nope.yaml"),
                "--no-enrich",
            ],
        )

        assert result.exit_code != 0
        assert "does not exist" in _clean_output(result.output)
        # Graph must not have been invoked with a missing style path.
        mock_build.return_value.invoke.assert_not_called()


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
