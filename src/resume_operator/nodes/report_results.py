"""Node: Save optimization results to JSON + write a human-readable diff.md.

When `state.output_dir` is set (the normal CLI path), all artefacts go inside
that folder so each run is self-contained and never overwrites prior runs.
Falls back to the legacy `data/results.json` + `data/diff.md` paths when no
output_dir is provided (used by tests and direct graph invocations).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from resume_operator.state import ResumeOptimizerState
from resume_operator.tools.diff_renderer import render_diff
from resume_operator.tools.source_index import build_source_index

logger = logging.getLogger(__name__)

# Legacy fallback paths used when `state.output_dir` is empty.
RESULTS_PATH = Path("data/results.json")
DIFF_PATH = Path("data/diff.md")


def report_results(state: ResumeOptimizerState) -> dict[str, Any]:
    """Compile and save the full optimization report into the per-run folder."""
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
            "output_dir": state.output_dir,
            "output_path": state.output_path,
            "errors": list(state.errors),
        }

        results_path, diff_path, tailored_path = _resolve_paths(state)

        results_path.parent.mkdir(parents=True, exist_ok=True)
        with results_path.open("w") as f:
            json.dump(report, f, indent=2)

        wrote_diff = False
        wrote_tailored = False
        if state.tailored_resume.items:
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            index = build_source_index(state.master, state.facts)
            diff_path.write_text(render_diff(state.tailored_resume, index), encoding="utf-8")
            wrote_diff = True

            tailored_path.parent.mkdir(parents=True, exist_ok=True)
            tailored_path.write_text(
                yaml.safe_dump(
                    state.tailored_resume.model_dump(),
                    sort_keys=False,
                    allow_unicode=True,
                    width=100,
                ),
                encoding="utf-8",
            )
            wrote_tailored = True

    except Exception as exc:
        logger.error("report_results: failed: %s", exc)
        errors.append(f"report_results: failed: {exc}")
        return {"errors": errors}

    extras: list[str] = []
    if wrote_diff:
        extras.append(str(diff_path))
    if wrote_tailored:
        extras.append(str(tailored_path))
    extras_msg = (" + " + ", ".join(extras)) if extras else ""
    logger.info("report_results: completed — wrote %s%s", results_path, extras_msg)

    result: dict[str, Any] = {"report": report}
    if errors != list(state.errors):
        result["errors"] = errors
    return result


def _resolve_paths(state: ResumeOptimizerState) -> tuple[Path, Path, Path]:
    """Return (results_json, diff_md, tailored_yaml) paths for this run."""
    if state.output_dir:
        out = Path(state.output_dir)
        return out / "results.json", out / "diff.md", out / "tailored.yaml"
    return RESULTS_PATH, DIFF_PATH, DIFF_PATH.parent / "tailored.yaml"
