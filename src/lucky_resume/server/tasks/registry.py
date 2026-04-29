"""In-process task registry — one `TaskHandle` per running task.

The registry is a dict keyed by `task_id`. Each entry holds the live
`Task` snapshot plus the runtime plumbing a flow needs:

- `consumers` — set of `asyncio.Queue`s, one per attached WebSocket.
  When an event is emitted, it's enqueued on every consumer queue
  (broadcast). Consumers detach by removing their queue.
- `reply_queue` — `queue.Queue` the prompter blocks on. The WS handler
  (or a `POST /api/tasks/{id}/reply`) drops the user's answer here.
- `cancel_event` — `threading.Event` that the runner / nodes can poll
  to bail out cooperatively when a `cancel` is requested.
- `loop` — the asyncio event loop the WS endpoints live on. The flow
  runs in a `to_thread`, so cross-thread enqueueing uses
  `loop.call_soon_threadsafe(queue.put_nowait, ...)`.

Persistence is layered: the registry is the live picture, `storage`
owns disk. The sink + lifecycle hooks call `storage.save(handle.task)`
at meaningful boundaries (status transitions, every Nth event,
flow completion).
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import Any

from lucky_resume.server.tasks import storage
from lucky_resume.server.tasks.model import (
    TERMINAL_STATUSES,
    PendingPrompt,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# Flush to disk every N events even when status isn't changing — caps
# event-log loss to N events if the process is killed hard.
EVENT_FLUSH_EVERY = 5


class TaskHandle:
    """Per-task runtime state.

    Owns the in-memory `Task`, the async fan-out machinery, and the
    blocking reply queue used by `TaskPrompter`.
    """

    def __init__(self, task: Task, loop: asyncio.AbstractEventLoop) -> None:
        self.task = task
        self.loop = loop
        self.consumers: set[asyncio.Queue[dict[str, Any]]] = set()
        self.cancel_event = threading.Event()
        self.asyncio_task: asyncio.Task[Any] | None = None
        self._lock = threading.Lock()
        self._events_since_flush = 0
        self._next_prompt_seq = 0
        # Per-prompt reply slot. `_current_reply` is a fresh queue allocated
        # by `begin_prompt` and consumed by the prompter; `_current_reply_seq`
        # is the prompt_seq replies must reference. Stale or seq-mismatched
        # replies are rejected by `deposit_reply`.
        self._current_reply: queue.Queue[dict[str, Any]] | None = None
        self._current_reply_seq: int | None = None

    # --- attachment ---------------------------------------------------------

    def attach(self) -> asyncio.Queue[dict[str, Any]]:
        """Register a new consumer queue. Caller must `detach` it later."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._lock:
            self.consumers.add(q)
        return q

    def detach(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self.consumers.discard(q)

    # --- event log ----------------------------------------------------------

    def record_event(self, event: dict[str, Any]) -> None:
        """Append an event, broadcast to consumers, flush every N events.

        Called from the worker thread. Cross-thread queue puts are
        scheduled on the asyncio loop via `call_soon_threadsafe`.
        """
        with self._lock:
            self.task.events.append(event)
            consumers = list(self.consumers)
            self._events_since_flush += 1
            should_flush = self._events_since_flush >= EVENT_FLUSH_EVERY
            if should_flush:
                self._events_since_flush = 0

        for q in consumers:
            self._post_to_consumer(q, event)

        if should_flush:
            self._flush()

    def _post_to_consumer(
        self, q: asyncio.Queue[dict[str, Any]], event: dict[str, Any]
    ) -> None:
        try:
            self.loop.call_soon_threadsafe(q.put_nowait, event)
        except RuntimeError:
            # Loop has shut down — consumer is gone, nothing to do.
            pass

    def broadcast(self, event: dict[str, Any]) -> None:
        """Fan-out without storing — used for transient signals like cancel
        notifications. Most events should go through `record_event`."""
        with self._lock:
            consumers = list(self.consumers)
        for q in consumers:
            self._post_to_consumer(q, event)

    # --- status transitions -------------------------------------------------

    def set_status(self, status: TaskStatus) -> None:
        with self._lock:
            self.task.status = status
        self._flush()
        self._broadcast_status()

    def set_started(self, at: float) -> None:
        with self._lock:
            self.task.started_at = at
            self.task.status = "running"
        self._flush()
        self._broadcast_status()

    def set_completed(self, result: dict[str, Any], at: float) -> None:
        with self._lock:
            self.task.result = result
            self.task.status = "completed"
            self.task.ended_at = at
            self.task.pending_prompt = None
        self._flush()
        self._broadcast_status()

    def set_failed(self, error: str, at: float) -> None:
        with self._lock:
            self.task.error = error
            self.task.status = "failed"
            self.task.ended_at = at
            self.task.pending_prompt = None
        self._flush()
        self._broadcast_status()

    def set_cancelled(self, at: float) -> None:
        with self._lock:
            self.task.status = "cancelled"
            self.task.ended_at = at
            self.task.pending_prompt = None
        self._flush()
        self._broadcast_status()

    def set_pending_prompt(self, prompt: PendingPrompt | None) -> None:
        with self._lock:
            self.task.pending_prompt = prompt
            if prompt is not None:
                self.task.status = "awaiting_input"
            elif self.task.status == "awaiting_input":
                self.task.status = "running"
        self._flush()
        self._broadcast_status()

    def _broadcast_status(self) -> None:
        """Notify live consumers that lifecycle state changed.

        Keeps the snapshot-then-stream protocol coherent: late-attaching
        clients see status in their snapshot; clients attached the whole
        time see live `task_status` frames as the task progresses.
        Status events are not added to `task.events` — they're derivable
        from the snapshot, so replaying them would double-count.
        """
        with self._lock:
            payload: dict[str, Any] = {
                "type": "task_status",
                "status": self.task.status,
                "pending_prompt": (
                    self.task.pending_prompt.model_dump()
                    if self.task.pending_prompt is not None
                    else None
                ),
                "result": self.task.result,
                "error": self.task.error,
                "started_at": self.task.started_at,
                "ended_at": self.task.ended_at,
            }
        self.broadcast(payload)

    def next_prompt_seq(self) -> int:
        with self._lock:
            self._next_prompt_seq += 1
            return self._next_prompt_seq

    def is_terminal(self) -> bool:
        return self.task.status in TERMINAL_STATUSES

    def request_cancel(self) -> None:
        """Flag the task for cancellation and wake any pending prompt.

        Nodes that want to be cancellation-aware can poll
        `cancel_event.is_set()` at safe boundaries. If the task is
        currently parked on a prompt, we shove a sentinel into the
        reply slot so the prompter can raise `PrompterCancelled`
        immediately instead of waiting for an answer that won't come.
        """
        self.cancel_event.set()
        with self._lock:
            target = self._current_reply
            self._current_reply = None
            self._current_reply_seq = None
        if target is not None:
            target.put_nowait({"_cancelled": True})

    # --- prompts ------------------------------------------------------------

    def begin_prompt(self, seq: int) -> queue.Queue[dict[str, Any]]:
        """Allocate a fresh reply slot for an upcoming prompt.

        The prompter calls this before broadcasting the prompt event,
        then blocks on `q.get()`. `deposit_reply` puts on this same
        queue when a reply with matching `seq` arrives.
        """
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
        with self._lock:
            self._current_reply = q
            self._current_reply_seq = seq
        return q

    def end_prompt(self) -> None:
        """Clear the reply slot — called after the prompter resumes."""
        with self._lock:
            self._current_reply = None
            self._current_reply_seq = None

    def deposit_reply(self, seq: int, value: Any) -> bool:
        """Hand a user reply to the waiting prompter.

        Returns False when no prompt is active or the seq doesn't match
        the one currently expected (stale reply / race between two
        attached consumers — first valid reply wins, the second sees
        the slot already cleared).
        """
        with self._lock:
            if self._current_reply is None or self._current_reply_seq != seq:
                return False
            target = self._current_reply
            self._current_reply = None
            self._current_reply_seq = None
        try:
            target.put_nowait({"value": value})
        except queue.Full:
            return False
        return True

    # --- persistence --------------------------------------------------------

    def _flush(self) -> None:
        try:
            storage.save(self.task)
        except Exception as exc:
            logger.warning("failed to flush task %s to disk: %s", self.task.id, exc)


class TaskRegistry:
    """In-process map of running tasks.

    Tasks live here while running and (briefly) after completion until
    GC. Persistence is independent — `storage` knows about everything,
    even tasks that never made it into the registry (e.g. tasks
    rehydrated from disk on restart that aren't currently running).
    """

    def __init__(self) -> None:
        self._handles: dict[str, TaskHandle] = {}
        self._lock = threading.Lock()

    def register(self, handle: TaskHandle) -> None:
        with self._lock:
            self._handles[handle.task.id] = handle

    def get(self, task_id: str) -> TaskHandle | None:
        with self._lock:
            return self._handles.get(task_id)

    def drop(self, task_id: str) -> None:
        with self._lock:
            self._handles.pop(task_id, None)

    def all(self) -> list[TaskHandle]:
        with self._lock:
            return list(self._handles.values())


_registry = TaskRegistry()


def get_registry() -> TaskRegistry:
    """Module-level singleton used by routes and runner."""
    return _registry
