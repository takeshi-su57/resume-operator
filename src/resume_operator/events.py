"""Structured event emission hook for nodes and flows.

Nodes and flows that want to surface progress to a UI call
`emit(NodeEvent(...))`. If no sink is bound to the current context (the
CLI case), the call is a no-op — zero overhead. The FastAPI server
(Phase 1) binds a sink that forwards events over a websocket so the React
frontend can render a live node timeline.

The sink is stored in a `contextvars.ContextVar` so multiple concurrent
sessions (one per websocket connection) never cross-contaminate each
other's event streams.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import time
from typing import Any, Literal, Protocol

EventPhase = Literal["start", "end", "progress", "error"]


@dataclass
class NodeEvent:
    """One structured event emitted from a node, flow, or LLM call.

    `node` is the emitter's name (e.g. `"ats_score"`, `"approval_loop"`).
    `phase` is `"start"` / `"end"` for lifecycle, `"progress"` for
    incremental updates, `"error"` for failures. `data` is free-form JSON
    the frontend can render (score values, proposal counts, file paths,
    etc.).
    """

    node: str
    phase: EventPhase
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time)


class EventSink(Protocol):
    """Target an event flows to. Server binds a websocket-backed sink."""

    def emit(self, event: NodeEvent) -> None: ...


_current_sink: ContextVar[EventSink | None] = ContextVar("resume_operator_event_sink", default=None)


def emit(event: NodeEvent) -> None:
    """Publish `event` to the current sink if one is bound, else no-op."""
    sink = _current_sink.get()
    if sink is not None:
        sink.emit(event)


@contextmanager
def bind_sink(sink: EventSink):  # type: ignore[no-untyped-def]
    """Bind `sink` as the active sink for the duration of the `with` block.

    Server route handlers wrap their graph invocation with this so the
    per-request websocket gets its own isolated event stream. The
    `ContextVar` token is reset on exit to prevent leaks across
    concurrent requests.
    """
    token = _current_sink.set(sink)
    try:
        yield sink
    finally:
        _current_sink.reset(token)
