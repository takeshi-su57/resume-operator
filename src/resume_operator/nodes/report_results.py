"""Node: Save optimization results to JSON + write a human-readable diff.md."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from resume_operator.state import ResumeOptimizerState
from resume_operator.tools.diff_renderer import render_diff
from resume_operator.tools.source_index import build_source_index

logger = logging.getLogger(__name__)

RESULTS_PATH = Path("data/results.json")
DIFF_PATH = Path("data/diff.md")


def report_results(state: ResumeOptimizerState) -> dict[str, Any]:
    """Compile and save the full optimization report.

    Writes:
      - `data/results.json` — machine-readable summary + tailored items
      - `data/diff.md` — human-readable diff (when tailoring ran)
    """
    logger.info("report_results: starting")
    errors: list[str] = list(state.errors)

    try:
        optimization_skipped = not state.tailored_resume.items
        report: dict[str, object] = {
            "timestamp": datetime.now().isoformat(),
            "resume_path": state.resume_path,
            "master_path": state.master_path,
            "facts_path": state.facts_path,
            "job_description_path": state.job_description_path,
            "ats_score": state.ats_score.model_dump(),
            "gap_analysis": state.gap_analysis.model_dump(),
            "optimization_skipped": optimization_skipped,
            "optimization_changes": state.optimized_resume.changes_made,
            "tailored_resume": state.tailored_resume.model_dump(),
            "output_path": state.output_path,
            "errors": list(state.errors),
        }

        results_path = RESULTS_PATH
        results_path.parent.mkdir(parents=True, exist_ok=True)
        with results_path.open("w") as f:
            json.dump(report, f, indent=2)

        diff_path: Path | None = None
        if state.tailored_resume.items:
            diff_path = DIFF_PATH
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            index = build_source_index(state.master, state.facts)
            diff_path.write_text(render_diff(state.tailored_resume, index), encoding="utf-8")

    except Exception as exc:
        logger.error("report_results: failed: %s", exc)
        errors.append(f"report_results: failed: {exc}")
        return {"errors": errors}

    logger.info(
        "report_results: completed — wrote %s%s",
        results_path,
        f" and {diff_path}" if diff_path else "",
    )

    result: dict[str, Any] = {"report": report}
    if errors != list(state.errors):
        result["errors"] = errors
    return result
