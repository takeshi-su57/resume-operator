"""`WebSocketPrompter` — drives interactive flows over a FastAPI WebSocket.

The flows (`flows.approval`, `flows.enrich`, `tools.approval_flow`,
`tools.enrich.run_interactive_session`) call blocking `Prompter`
methods — `confirm`, `choose`, `text`, `render_*`, `status`. This
implementation bridges those sync calls to an async WebSocket:

- Outbound (`render_proposal`, `notice`, etc.): the prompter's sync
  method schedules an `await ws.send_json(...)` on the server's event
  loop via `asyncio.run_coroutine_threadsafe`.
- Inbound (`confirm`, `choose`, `text`): the prompter's sync method
  sends its prompt message, then blocks on `queue.Queue.get()` waiting
  for a reply that the WS handler deposits when the client answers.

This lets the flows keep their existing synchronous shape while running
in a background thread (`asyncio.to_thread`), with the main event loop
free to handle other concurrent WS sessions.
"""

from __future__ import annotations

import asyncio
import queue
import time
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from resume_operator.events import EventSink, NodeEvent

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import WebSocket

    from resume_operator.state import Proposal
    from resume_operator.tools.enrich import PolishedFactLLMOutput, Question


def _dump(obj: Any) -> Any:
    """Best-effort JSON-ready dict for a domain object."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return obj


class WebSocketPrompter:
    """Drives the Prompter protocol over a FastAPI WebSocket.

    Instantiated per-session by the WS route handler, which also feeds
    client replies into `deposit_reply`. The session runs the flow in a
    background thread — this prompter's methods are called from that
    thread.
    """

    def __init__(self, ws: WebSocket, loop: asyncio.AbstractEventLoop) -> None:
        self._ws = ws
        self._loop = loop
        self._inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self._closed = False

    # --- bridge mechanics ---------------------------------------------------

    def _send(self, payload: dict[str, Any]) -> None:
        """Schedule `ws.send_json(payload)` on the server event loop.

        Called from the worker thread. Blocks until the send completes so
        the flow doesn't race ahead of its own render calls.
        """
        if self._closed:
            return
        future = asyncio.run_coroutine_threadsafe(self._ws.send_json(payload), self._loop)
        try:
            future.result(timeout=10)
        except Exception:
            # If send fails (closed socket, cancelled loop), mark the
            # session closed so subsequent calls short-circuit instead of
            # blowing up repeatedly.
            self._closed = True
            raise

    def _recv(self) -> dict[str, Any]:
        """Block on `queue.Queue.get()` for a client reply.

        WS handler calls `deposit_reply` when a `{"type": "reply", ...}`
        message arrives from the client. Raises `PrompterDisconnectedError` if
        the session has been closed.
        """
        reply = self._inbox.get()
        if reply.get("_closed"):
            raise PrompterDisconnectedError()
        return reply

    def deposit_reply(self, message: dict[str, Any]) -> None:
        """Called by the WS handler when a client reply arrives."""
        self._inbox.put(message)

    def close(self) -> None:
        """Signal the prompter that the session is done. Any blocking
        `_recv` call wakes up and raises `PrompterDisconnectedError`."""
        self._closed = True
        self._inbox.put({"_closed": True})

    # --- Prompter: user decisions ------------------------------------------

    def confirm(self, message: str, *, default: bool = False) -> bool:
        self._send({"type": "confirm", "message": message, "default": default})
        reply = self._recv()
        value = reply.get("value", default)
        return bool(value)

    def choose(self, message: str, choices: list[str], *, default: str) -> str:
        self._send(
            {
                "type": "choose",
                "message": message,
                "choices": choices,
                "default": default,
            }
        )
        reply = self._recv()
        value = reply.get("value", default)
        return str(value).lower()

    def text(self, message: str, *, default: str = "") -> str:
        self._send({"type": "text", "message": message, "default": default})
        reply = self._recv()
        value = reply.get("value", default) or ""
        return str(value).strip()

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

    def render_iteration_header(self, *, iteration: int, max_iter: int, score: float) -> None:
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


class PrompterDisconnectedError(RuntimeError):
    """Raised from a `Prompter` method when the WS client has disconnected
    mid-session. Caught by the session runner to cleanly abort the flow."""


class WebSocketEventSink(EventSink):
    """Forwards `NodeEvent`s over the same WebSocket as the prompter.

    The node-event channel is one-way — the frontend just renders the
    live node timeline — so we don't need a reply queue here.
    """

    def __init__(self, prompter: WebSocketPrompter) -> None:
        self._prompter = prompter

    def emit(self, event: NodeEvent) -> None:
        self._prompter._send(
            {
                "type": "node_event",
                "node": event.node,
                "phase": event.phase,
                "data": event.data,
                "timestamp": event.timestamp,
            }
        )
