"""Tests for the report_results node."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from resume_operator.nodes.report_results import report_results
from resume_operator.state import OptimizedResume, ResumeOptimizerState


def _setup_state(state: ResumeOptimizerState) -> None:
    """Populate fields not set by the sample_state fixture."""
    state.optimized_resume = OptimizedResume(
        sections={"summary": "Optimized summary.", "skills": "Python, AWS"},
        changes_made=["Added Kubernetes to skills", "Rewrote summary"],
    )
    state.output_path = "data/optimized_resume.pdf"


EXPECTED_KEYS = {
    "timestamp",
    "resume_path",
    "job_description_path",
    "ats_score",
    "gap_analysis",
    "optimization_changes",
    "output_path",
    "errors",
}


class TestReportResults:
    def test_writes_json_report(self, sample_state: ResumeOptimizerState, tmp_path: Path) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "data" / "results.json"

        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
            result = report_results(sample_state)

        assert results_file.exists()
        data = json.loads(results_file.read_text())
        assert isinstance(data, dict)
        assert "report" in result

    def test_report_contains_all_fields(
        self, sample_state: ResumeOptimizerState, tmp_path: Path
    ) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "data" / "results.json"

        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
            result = report_results(sample_state)

        report = result["report"]
        assert set(report.keys()) == EXPECTED_KEYS
        assert report["ats_score"]["score"] == 0.72
        assert len(report["gap_analysis"]["gaps"]) > 0
        assert report["optimization_changes"] == [
            "Added Kubernetes to skills",
            "Rewrote summary",
        ]
        assert report["resume_path"] == "test_resume.pdf"
        assert report["output_path"] == "data/optimized_resume.pdf"
        # Validate timestamp is parseable ISO format
        datetime.fromisoformat(report["timestamp"])

    def test_creates_data_directory(
        self, sample_state: ResumeOptimizerState, tmp_path: Path
    ) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "nonexistent" / "subdir" / "results.json"

        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
            report_results(sample_state)

        assert results_file.parent.exists()
        assert results_file.exists()

    def test_handles_write_error(self, sample_state: ResumeOptimizerState, tmp_path: Path) -> None:
        _setup_state(sample_state)
        results_file = tmp_path / "data" / "results.json"

        with (
            patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file),
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
            patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file),
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

        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
            result = report_results(sample_state)

        allowed_keys = {"report", "errors"}
        assert set(result.keys()).issubset(allowed_keys)
        assert "resume" not in result
        assert "ats_score" not in result
