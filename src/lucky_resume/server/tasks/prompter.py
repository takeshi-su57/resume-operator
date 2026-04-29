"""`TaskPrompter` — drives interactive flows against a `TaskHandle`.

Replaces `WebSocketPrompter` for the task-registry path. Differences
from the legacy prompter:

- Output goes through `handle.record_event(...)` so every prompt /
  notice / status / render is **persisted** in the task's event log
  *and* fanned out to every attached consumer. Late-attaching clients
  see the full conversation by replaying `task.events`.
- Prompts (`confirm` / `choose` / `text`) carry a `prompt_seq` and
  set `task.pending_prompt`, then **block forever** on a per-prompt
  reply slot. Disconnects do *not* raise — the user can navigate away,
  come back hours later, and answer; the task simply parks in
  `awaiting_input` until any consumer (WS reply or
  `POST /api/tasks/{id}/reply`) supplies an answer.
- `request_cancel` on the handle wakes the slot with a sentinel,
  raising `PrompterCancelledError` so the flow unwinds cleanly.
"""

from __future__ import annotations

import time
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from lucky_resume.server.tasks.model import PendingPrompt
from lucky_resume.server.tasks.registry import TaskHandle

if TYPE_CHECKING:
    from collections.abc import Iterator

    from lucky_resume.state import Proposal
    from lucky_resume.tools.enrich import PolishedFactLLMOutput, Question


def _dump(obj: Any) -> Any:
    """Best-effort JSON-ready dict for a domain object."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return obj


class PrompterCancelledError(RuntimeError):
    """Raised from a `TaskPrompter` method when the task is cancelled.

    Caught by the runner, which transitions the task to `cancelled`.
    Distinct from `PrompterDisconnectedError` (used by the legacy
    `WebSocketPrompter` for client disconnects) — task prompters never
    raise on a bare disconnect; only an explicit cancel triggers this.
    """


class TaskPrompter:
    """Drives the Prompter protocol against a `TaskHandle`.

    Methods are called from the worker thread via `asyncio.to_thread`;
    cross-thread enqueueing into asyncio consumer queues is handled by
    `TaskHandle.record_event` via `loop.call_soon_threadsafe`.
    """

    def __init__(self, handle: TaskHandle) -> None:
        self._handle = handle

    # --- bridge mechanics ---------------------------------------------------

    def _send(self, payload: dict[str, Any]) -> None:
        """Append an outgoing message to the event log + broadcast to consumers.

        Cancellation is checked here so a flow that's emitting renders
        in a tight loop notices the cancel quickly even if no prompt is
        active.
        """
        if self._handle.cancel_event.is_set():
            raise PrompterCancelledError()
        self._handle.record_event(payload)

    def _wait_reply(self, prompt: PendingPrompt, default: Any) -> Any:
        """Park on a fresh reply slot for `prompt`. Blocks indefinitely."""
        slot = self._handle.begin_prompt(prompt.prompt_seq)
        self._handle.set_pending_prompt(prompt)
        try:
            reply = slot.get()  # blocks forever — user pace, not server pace
        finally:
            self._handle.end_prompt()
            self._handle.set_pending_prompt(None)
        if reply.get("_cancelled"):
            raise PrompterCancelledError()
        return reply.get("value", default)

    # --- Prompter: user decisions ------------------------------------------

    def confirm(self, message: str, *, default: bool = False) -> bool:
        seq = self._handle.next_prompt_seq()
        self._send(
            {
                "type": "confirm",
                "prompt_seq": seq,
                "message": message,
                "default": default,
            }
        )
        prompt = PendingPrompt(
            kind="confirm", prompt_seq=seq, message=message, default=default
        )
        value = self._wait_reply(prompt, default)
        return bool(value)

    def choose(self, message: str, choices: list[str], *, default: str) -> str:
        seq = self._handle.next_prompt_seq()
        self._send(
            {
                "type": "choose",
                "prompt_seq": seq,
                "message": message,
                "choices": list(choices),
                "default": default,
            }
        )
        prompt = PendingPrompt(
            kind="choose",
            prompt_seq=seq,
            message=message,
            default=default,
            choices=list(choices),
        )
        value = self._wait_reply(prompt, default)
        return str(value).lower()

    def text(self, message: str, *, default: str = "") -> str:
        seq = self._handle.next_prompt_seq()
        self._send(
            {
                "type": "text",
                "prompt_seq": seq,
                "message": message,
                "default": default,
            }
        )
        prompt = PendingPrompt(
            kind="text", prompt_seq=seq, message=message, default=default
        )
        value = self._wait_reply(prompt, default)
        return str(value or "").strip()

    # --- Prompter: domain rendering ----------------------------------------

    def render_proposal(self, proposal: Proposal, *, index: int, total: int) -> None:
        self._send(
            {
                "type": "render_proposal",
                "proposal": _dump(proposal),
                "index": index,
                "total": total,
            }
        )

    def render_iteration_header(
        self, *, iteration: int, max_iter: int, score: float
    ) -> None:
        self._send(
            {
                "type": "render_iteration_header",
                "iteration": iteration,
                "max_iter": max_iter,
                "score": score,
            }
        )

    def render_question(self, question: Question, *, index: int, total: int) -> None:
        self._send(
            {
                "type": "render_question",
                "question": _dump(question),
                "index": index,
                "total": total,
            }
        )

    def render_polished(self, polished: PolishedFactLLMOutput) -> None:
        self._send({"type": "render_polished", "polished": _dump(polished)})

    # --- Prompter: generic rendering ---------------------------------------

    def notice(self, message: str, *, style: str = "") -> None:
        self._send({"type": "notice", "message": message, "style": style})

    def panel(self, message: str, *, title: str, style: str = "") -> None:
        self._send({"type": "panel", "message": message, "title": title, "style": style})

    # --- Prompter: long-running operations ---------------------------------

    def status(self, message: str) -> AbstractContextManager[None]:
        return self._status_cm(message)

    @contextmanager
    def _status_cm(self, message: str) -> Iterator[None]:
        self._send({"type": "status_start", "message": message, "at": time.time()})
        try:
            yield
        finally:
            self._send({"type": "status_end", "at": time.time()})
