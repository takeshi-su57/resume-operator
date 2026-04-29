"""`WS /api/ws/bootstrap` — PDF → master YAML with interactive interview.

Mirrors the CLI `bootstrap` command (#60, #70). Client sends `{"type":
"start", "params": {"resume": "...", "output": "...", "skip_interview":
false}}`, then responds to the interview prompts (headline, links,
per-role tech, skill groups) over the same WebSocket.

The parse-resume step itself is non-interactive and runs up front
(before any prompter traffic); if the parse fails, the session emits an
`error` and closes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket
from pydantic import BaseModel

from lucky_resume.nodes.parse_resume import parse_resume as parse_resume_node
from lucky_resume.server.session_runner import run_flow_over_ws
from lucky_resume.server.ws_prompter import WebSocketPrompter
from lucky_resume.state import ResumeMaster, ResumeOptimizerState
from lucky_resume.tools.bootstrap_interview import run_interview
from lucky_resume.tools.master_resume import save_master

router = APIRouter()


class BootstrapParams(BaseModel):
    resume: str  # path to resume PDF
    output: str = "data/master_resume.yaml"
    skip_interview: bool = False


class BootstrapResult(BaseModel):
    output_path: str
    master: ResumeMaster
    errors: list[str]


def _execute_bootstrap(raw_params: dict[str, Any], prompter: WebSocketPrompter) -> BootstrapResult:
    params = BootstrapParams.model_validate(raw_params)

    resume_path = Path(params.resume)
    if not resume_path.exists():
        raise RuntimeError(f"resume path not found: {params.resume}")
    if resume_path.suffix.lower() != ".pdf":
        raise RuntimeError("resume must be a .pdf file")

    with prompter.status("Bootstrapping master resume from PDF..."):
        state = ResumeOptimizerState(resume_path=str(resume_path))
        result = parse_resume_node(state)

    errors: list[str] = list(result.get("errors", []))
    if errors:
        raise RuntimeError(f"parse-resume failed: {'; '.join(errors)}")

    master: ResumeMaster = result["master"]

    # The GUI always runs the interview — skipping it is a deliberate client
    # choice (the desktop app can expose a "Skip interview" toggle in the UI).
    if not params.skip_interview:
        master = run_interview(master, prompter=prompter)

    output_path = Path(params.output)
    save_master(master, output_path)

    headline_status = "set" if master.headline else "empty (tailor writes one per JD)"
    prompter.panel(
        f"[bold]Wrote:[/bold] {output_path}\n"
        f"[bold]Experience entries:[/bold] {len(master.experience)}\n"
        f"[bold]Education entries:[/bold] {len(master.education)}\n"
        f"[bold]Skills:[/bold] {len(master.all_skills())}\n"
        f"[bold]Links:[/bold] {len(master.links)}\n"
        f"[bold]Headline:[/bold] {headline_status}",
        title="Master resume bootstrapped",
        style="green",
    )

    return BootstrapResult(output_path=str(output_path), master=master, errors=errors)


def _serialize_bootstrap_result(result: BootstrapResult) -> dict[str, Any]:
    return result.model_dump()


@router.websocket("/ws/bootstrap")
async def ws_bootstrap(ws: WebSocket) -> None:
    await run_flow_over_ws(
        ws,
        flow_fn=_execute_bootstrap,
        serialize_result=_serialize_bootstrap_result,
    )
