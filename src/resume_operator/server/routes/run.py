"""`WS /api/ws/run` — full pipeline with interactive approval loop and auto-enrich.

Mirrors the CLI `run` command end-to-end: load master/resume, tailor,
optionally enrich, optionally approve iteratively, finalize. The client
opens a WebSocket, sends one `{"type": "start", "params": {...}}`
message, and then responds to prompter messages (`confirm` / `choose` /
`text`) until `{"type": "done", "result": {...}}` arrives.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket
from pydantic import BaseModel, Field

from resume_operator.config import get_settings
from resume_operator.flows.approval import run_approval_loop
from resume_operator.flows.enrich import DEFAULT_FACTS_PATH, run_auto_enrich
from resume_operator.graph import build_finalize_graph, build_tailor_graph
from resume_operator.server.session_runner import run_flow_over_ws
from resume_operator.server.ws_prompter import WebSocketPrompter
from resume_operator.state import ResumeOptimizerState, TailoredResume
from resume_operator.tools.output_dir import resolve_output_dir

logger = logging.getLogger(__name__)

router = APIRouter()


class RunParams(BaseModel):
    """Subset of the CLI `run` command's flags that apply to a GUI session."""

    master: str | None = None
    resume: str | None = None  # legacy PDF path
    facts: str | None = None
    job: str  # required
    output: str | None = None  # parent dir, defaults to data/applications/
    style: str | None = None
    no_enrich: bool = False
    no_approve: bool = False
    max_iter: int | None = Field(default=None, ge=1)


def _should_offer_enrich(
    result: dict[str, Any], *, no_enrich: bool, master_path: str | None
) -> bool:
    """GUI equivalent of `main._should_offer_enrich` — no TTY check, the
    WebSocket itself is the interactivity signal."""
    if no_enrich or master_path is None:
        return False
    report = result.get("report", {})
    if isinstance(report, dict) and report.get("optimization_skipped"):
        return False
    tailored = result.get("tailored_resume")
    if not isinstance(tailored, TailoredResume) or not tailored.items:
        return False
    threshold = get_settings().enrich_threshold
    return len(tailored.kept_or_reworded()) < threshold


def _should_run_approval_loop(result: dict[str, Any], *, no_approve: bool) -> bool:
    if no_approve:
        return False
    tailored = result.get("tailored_resume")
    return isinstance(tailored, TailoredResume) and bool(tailored.items)


def _build_initial(params: RunParams) -> dict[str, str]:
    jd_path = Path(params.job)
    jd_text = jd_path.read_text(encoding="utf-8") if jd_path.exists() else ""
    output_dir = resolve_output_dir(
        parent=Path(params.output) if params.output else None,
        jd_path=jd_path,
        jd_text=jd_text,
    )
    initial: dict[str, str] = {
        "job_description_path": str(jd_path),
        "output_dir": str(output_dir),
        "output_path": str(output_dir / "resume.pdf"),
    }
    if params.master:
        initial["master_path"] = params.master
    elif params.resume:
        initial["resume_path"] = params.resume
    if params.facts:
        initial["facts_path"] = params.facts
    elif DEFAULT_FACTS_PATH.exists() and params.master:
        initial["facts_path"] = str(DEFAULT_FACTS_PATH)
    if params.style:
        initial["style_path"] = params.style
    return initial


def _execute_run(raw_params: dict[str, Any], prompter: WebSocketPrompter) -> dict[str, Any]:
    """Sync mirror of the CLI `run` command — drives the same flows with
    a `WebSocketPrompter` instead of `RichPrompter`. Runs in a background
    thread via `run_flow_over_ws`."""
    params = RunParams.model_validate(raw_params)
    initial = _build_initial(params)
    jd_path = Path(params.job)
    jd_text = jd_path.read_text(encoding="utf-8") if jd_path.exists() else ""

    tailor_graph = build_tailor_graph()
    finalize_graph = build_finalize_graph()

    with prompter.status("Running optimization pipeline..."):
        result = tailor_graph.invoke(initial)

    # --- Auto-enrich (#56/#64) ---
    resolved_facts_str = initial.get("facts_path")
    resolved_facts = Path(resolved_facts_str) if resolved_facts_str else None
    if params.master and _should_offer_enrich(
        result, no_enrich=params.no_enrich, master_path=params.master
    ):
        if run_auto_enrich(
            prompter=prompter,
            master_path=Path(params.master),
            facts_path=resolved_facts,
            jd_text=jd_text,
        ):
            prompter.notice("Re-running optimization with enriched facts...", style="cyan")
            if resolved_facts is None:
                resolved_facts = DEFAULT_FACTS_PATH
                initial["facts_path"] = str(resolved_facts)
            with prompter.status("Re-running pipeline..."):
                result = tailor_graph.invoke(initial)

    # --- Iterative approval loop (#78) ---
    if _should_run_approval_loop(result, no_approve=params.no_approve):
        effective_max_iter = (
            params.max_iter if params.max_iter is not None else get_settings().resume_max_iterations
        )
        result = run_approval_loop(
            prompter=prompter,
            tailor_graph=tailor_graph,
            initial_result=result,
            initial_input=initial,
            max_iterations=effective_max_iter,
        )

    # --- Finalize: render PDF + write artifacts ---
    with prompter.status("Rendering PDF and writing outputs..."):
        result = finalize_graph.invoke(result)

    return result


def _serialize_run_result(result: dict[str, Any]) -> dict[str, Any]:
    """Turn a `ResumeOptimizerState`-shaped dict into plain JSON for the client.

    The graph returns a mix of Pydantic models and scalars; route them
    all through `ResumeOptimizerState.model_validate` + `model_dump` so
    the frontend gets a consistent shape.
    """
    try:
        state = ResumeOptimizerState.model_validate(result)
        return state.model_dump(exclude_none=False)
    except Exception:
        # Fall back to a loose dump — better to surface a partial result
        # than crash on serialization right at the end.
        logger.warning("run result serialization fell back to shallow dump")
        return {k: (v.model_dump() if hasattr(v, "model_dump") else v) for k, v in result.items()}


@router.websocket("/ws/run")
async def ws_run(ws: WebSocket) -> None:
    await run_flow_over_ws(ws, flow_fn=_execute_run, serialize_result=_serialize_run_result)
