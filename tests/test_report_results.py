"""Tests for the report_results node."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from lucky_resume.nodes.report_results import report_results
from lucky_resume.state import (
    OptimizedResume,
    ResumeOptimizerState,
    TailoredItem,
    TailoredResume,
)


def _setup_state(state: ResumeOptimizerState) -> None:
    """Populate fields not set by the sample_state fixture."""
    state.optimized_resume = OptimizedResume(
        sections={"summary": "Optimized summary.", "skills": "Python, AWS"},
        changes_made=["keep: master:summary", "reword: master:exp-1-b1"],
    )
    state.tailored_resume = TailoredResume(
        items=[
            TailoredItem(source_id="master:summary", action="keep", original_text="summary text"),
            TailoredItem(
                source_id="master:exp-1-b1",
                action="reword",
                original_text="Led backend team",
                new_text="Led backend team on Kubernetes",
            ),
        ],
        notes=["Tightened backend emphasis."],
    )
    state.output_path = "data/optimized_resume.pdf"


EXPECTED_KEYS = {
    "timestamp",
    "resume_path",
    "master_path",
    "facts_path",
    "job_description_path",
    "ats_score",
    "gap_analysis",
    "optimization_skipped",
    "optimization_changes",
    "tailored_resume",
    "output_dir",
    "output_path",
    "errors",
}


class TestReportResults:
    def test_writes_json_report(self, sample_state: ResumeOptimizerState, tmp_path: Path) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "data" / "results.json"
        diff_file = tmp_path / "data" / "diff.md"

        with (
            patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file),
            patch("lucky_resume.nodes.report_results.DIFF_PATH", diff_file),
        ):
            result = report_results(sample_state)

        assert results_file.exists()
        assert diff_file.exists(), "diff.md should be written whenever tailored_resume has items"
        data = json.loads(results_file.read_text())
        assert isinstance(data, dict)
        assert "report" in result
        assert "tailored_resume" in data

    def test_diff_md_content(self, sample_state: ResumeOptimizerState, tmp_path: Path) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "data" / "results.json"
        diff_file = tmp_path / "data" / "diff.md"

        with (
            patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file),
            patch("lucky_resume.nodes.report_results.DIFF_PATH", diff_file),
        ):
            report_results(sample_state)

        body = diff_file.read_text(encoding="utf-8")
        assert "# Tailoring Diff" in body
        # The reworded item should show both before and after.
        assert "Led backend team on Kubernetes" in body
        assert "master:exp-1-b1" in body

    def test_report_contains_all_fields(
        self, sample_state: ResumeOptimizerState, tmp_path: Path
    ) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "data" / "results.json"
        diff_file = tmp_path / "data" / "diff.md"

        with (
            patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file),
            patch("lucky_resume.nodes.report_results.DIFF_PATH", diff_file),
        ):
            result = report_results(sample_state)

        report = result["report"]
        assert set(report.keys()) == EXPECTED_KEYS
        assert report["ats_score"]["score"] == 0.72
        assert report["resume_path"] == "test_resume.pdf"
        assert report["output_path"] == "data/optimized_resume.pdf"
        datetime.fromisoformat(report["timestamp"])

    def test_skips_diff_when_no_tailored_items(
        self, sample_state: ResumeOptimizerState, tmp_path: Path
    ) -> None:
        sample_state.output_path = "data/optimized_resume.pdf"
        # deliberately leave tailored_resume empty
        results_file = tmp_path / "data" / "results.json"
        diff_file = tmp_path / "data" / "diff.md"

        with (
            patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file),
            patch("lucky_resume.nodes.report_results.DIFF_PATH", diff_file),
        ):
            report_results(sample_state)

        assert results_file.exists()
        assert not diff_file.exists()

    def test_handles_write_error(self, sample_state: ResumeOptimizerState, tmp_path: Path) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "data" / "results.json"

        with (
            patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file),
            patch.object(Path, "open", side_effect=PermissionError("read-only")),
        ):
            result = report_results(sample_state)

        assert "errors" in result
        assert any("report_results: failed" in e for e in result["errors"])
        assert "report" not in result

    def test_preserves_existing_errors(
        self, sample_state: ResumeOptimizerState, tmp_path: Path
    ) -> None:
        _setup_state(sample_state)
        sample_state.errors = ["earlier failure"]
        results_file = tmp_path / "data" / "results.json"

        with (
            patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file),
            patch.object(Path, "open", side_effect=PermissionError("read-only")),
        ):
            result = report_results(sample_state)

        assert "earlier failure" in result["errors"]
        assert any("report_results: failed" in e for e in result["errors"])
        assert len(result["errors"]) == 2

    def test_returns_only_changed_fields(
        self, sample_state: ResumeOptimizerState, tmp_path: Path
    ) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "data" / "results.json"
        diff_file = tmp_path / "data" / "diff.md"

        with (
            patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file),
            patch("lucky_resume.nodes.report_results.DIFF_PATH", diff_file),
        ):
            result = report_results(sample_state)

        allowed_keys = {"report", "errors"}
        assert set(result.keys()).issubset(allowed_keys)

    def test_writes_into_output_dir_when_set(
        self, sample_state: ResumeOptimizerState, tmp_path: Path
    ) -> None:
        _setup_state(sample_state)
        out_dir = tmp_path / "data" / "applications" / "2026-04-21_acme"
        out_dir.mkdir(parents=True)
        sample_state.output_dir = str(out_dir)

        report_results(sample_state)

        # All artefacts go inside the per-application folder.
        assert (out_dir / "results.json").exists()
        assert (out_dir / "diff.md").exists()
        assert (out_dir / "tailored.yaml").exists()
        # Tailored YAML is parseable and contains the items we set up.
        import yaml

        loaded = yaml.safe_load((out_dir / "tailored.yaml").read_text(encoding="utf-8"))
        assert isinstance(loaded["items"], list)
        assert any(it["source_id"] == "master:summary" for it in loaded["items"])
