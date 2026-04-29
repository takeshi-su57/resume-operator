"""Task data model — on-disk + over-the-wire shape of a registered task.

A `Task` is a snapshot. The registry holds the live mutable copy; the
storage layer persists snapshots to disk; the WS `snapshot` frame ships
the full snapshot to a freshly-attached client so it can render
everything that happened before it connected.

Events are stored as plain dicts in the wire format already produced by
`WebSocketPrompter` / `WebSocketEventSink` (`{type, ...}`). That keeps
late-attach replay trivial — the snapshot's `events` list can be sent
verbatim, then live events stream in afterwards in the same shape.
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskKind = Literal["run", "score"]
TaskStatus = Literal[
    "queued",
    "running",
    "awaiting_input",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
]
TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset(
    {"completed", "failed", "cancelled", "interrupted"}
)


def new_task_id() -> str:
    """Generate a sortable task id.

    Format: `{millis-since-epoch:013d}-{8 hex chars}`. Lex-sortable by
    creation time (so listing tasks in `created_at` order is just a
    sorted directory scan), 22 chars total, no external deps.
    """
    millis = int(time.time() * 1000)
    return f"{millis:013d}-{secrets.token_hex(4)}"


class PendingPrompt(BaseModel):
    """User decision the task is currently blocked on."""

    kind: Literal["confirm", "choose", "text"]
    prompt_seq: int  # monotonic per task — answers must reference this
    message: str
    default: Any = None
    choices: list[str] | None = None


class Task(BaseModel):
    """A registered run or score, including its event history.

    `events` carries every server→client message produced for this task
    in the wire format clients already know how to render, so a freshly
    attached consumer can replay them and arrive at the same UI state
    as a consumer that's been attached the whole time.
    """

    id: str
    kind: TaskKind
    status: TaskStatus = "queued"
    params: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    pending_prompt: PendingPrompt | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    ended_at: float | None = None
    schema_version: int = 1
