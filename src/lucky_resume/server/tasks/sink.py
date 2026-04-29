"""`TaskSink` — `EventSink` that records events on a `TaskHandle`.

Bound via `bind_sink(TaskSink(handle))` for the duration of the flow.
Each `emit(NodeEvent)` becomes a wire-format dict appended to the task's
event log AND broadcast to every attached consumer queue. The wire
format mirrors `WebSocketEventSink`'s `node_event` payload so the
frontend type union (`NodeEventMessage` in `desktop/src/lib/events.ts`)
covers both code paths uniformly.
"""

from __future__ import annotations

from typing import Any

from lucky_resume.events import EventSink, NodeEvent
from lucky_resume.server.tasks.registry import TaskHandle


def node_event_payload(event: NodeEvent) -> dict[str, Any]:
    """Serialize a `NodeEvent` into the wire-format dict the frontend reads."""
    return {
        "type": "node_event",
        "node": event.node,
        "phase": event.phase,
        "data": event.data,
        "timestamp": event.timestamp,
    }


class TaskSink(EventSink):
    """Routes node events into a task's event log + live consumer fan-out."""

    def __init__(self, handle: TaskHandle) -> None:
        self._handle = handle

    def emit(self, event: NodeEvent) -> None:
        self._handle.record_event(node_event_payload(event))
