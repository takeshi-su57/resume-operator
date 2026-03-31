"""Node: Save optimization results to JSON."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from resume_operator.state import ResumeOptimizerState

logger = logging.getLogger(__name__)

RESULTS_PATH = Path("data/results.json")


def report_results(state: ResumeOptimizerState) -> dict[str, Any]:
    """Compile and save the full optimization report.

    Writes a JSON report to data/ with ATS scores, gap analysis,
    changes made, and any errors encountered.
    """
    logger.info("report_results: starting")
    errors: list[str] = list(state.errors)

    try:
        optimization_skipped = not state.optimized_resume.sections
        report: dict[str, object] = {
            "timestamp": datetime.now().isoformat(),
            "resume_path": state.resume_path,
            "job_description_path": state.job_description_path,
            "ats_score": state.ats_score.model_dump(),
            "gap_analysis": state.gap_analysis.model_dump(),
            "optimization_skipped": optimization_skipped,
            "optimization_changes": state.optimized_resume.changes_made,
            "output_path": state.output_path,
            "errors": list(state.errors),
        }

        output_path = RESULTS_PATH
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(report, f, indent=2)

    except Exception as exc:
        logger.error("report_results: failed: %s", exc)
        errors.append(f"report_results: failed: {exc}")
        return {"errors": errors}

    logger.info("report_results: completed — wrote %s", output_path)

    result: dict[str, Any] = {"report": report}
    if errors != list(state.errors):
        result["errors"] = errors
    return result
