"""Task registry — first-class persistent unit of work for runs and scores.

Each user-triggered run or score is registered as a `Task` with its own
`id`, lifecycle status, append-only event log, and result. The frontend
attaches to a task's WebSocket stream for live progress, can detach
(navigate away), and reattach later — the task keeps running on the
backend regardless. Tasks persist to disk so history survives sidecar
restarts.

The pieces:

- `model.Task` — the on-disk + over-the-wire shape.
- `storage` — JSON-per-task on disk (atomic writes).
- `registry.TaskRegistry` — in-process map of running tasks plus their
  consumer queues, reply queues, and cancel flags.
- `sink.TaskSink` — the `EventSink` implementation that fans events to
  attached consumers and persists them.
- `lifecycle` — startup scan that marks crashed tasks as `interrupted`.
- `runner` — spawns a flow under a bound TaskSink + TaskPrompter
  (added in Phase 2).
- `prompter.TaskPrompter` — pause-indefinitely prompter (Phase 2).
"""

from lucky_resume.server.tasks.model import (
    PendingPrompt,
    Task,
    TaskKind,
    TaskStatus,
    new_task_id,
)
from lucky_resume.server.tasks.registry import TaskHandle, TaskRegistry, get_registry
from lucky_resume.server.tasks.sink import TaskSink

__all__ = [
    "PendingPrompt",
    "Task",
    "TaskHandle",
    "TaskKind",
    "TaskRegistry",
    "TaskSink",
    "TaskStatus",
    "get_registry",
    "new_task_id",
]
