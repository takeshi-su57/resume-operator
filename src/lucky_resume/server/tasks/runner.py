"""`start_task` — register a new task and spawn its background flow.

Each task runs as `asyncio.to_thread(flow_fn, params, TaskPrompter)`
with a `TaskSink` bound for the duration. The task's `asyncio.Task`
wraps that thread so we can `cancel()` from the FastAPI loop. Result
serialization is per-kind; failures are recorded on the task and the
flow returns cleanly so the registry can persist a final snapshot.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from lucky_resume.events import bind_sink
from lucky_resume.flows.run_session import execute_run, serialize_run_result
from lucky_resume.flows.score_session import execute_score, serialize_score_result
from lucky_resume.server.tasks import storage
from lucky_resume.server.tasks.model import Task, TaskKind, new_task_id
from lucky_resume.server.tasks.prompter import PrompterCancelledError, TaskPrompter
from lucky_resume.server.tasks.registry import TaskHandle, get_registry
from lucky_resume.server.tasks.sink import TaskSink

logger = logging.getLogger(__name__)


FlowFn = Callable[[dict[str, Any], TaskPrompter], Any]
Serializer = Callable[[Any], dict[str, Any]]


def _select_flow(kind: TaskKind) -> tuple[FlowFn, Serializer]:
    if kind == "run":
        return execute_run, serialize_run_result
    if kind == "score":
        return execute_score, serialize_score_result
    raise ValueError(f"unknown task kind: {kind}")


def start_task(kind: TaskKind, params: dict[str, Any]) -> str:
    """Register a new task and spawn its background flow. Returns the task id."""
    loop = asyncio.get_running_loop()
    task = Task(id=new_task_id(), kind=kind, params=dict(params))
    handle = TaskHandle(task, loop)
    storage.save(task)
    get_registry().register(handle)
    handle.asyncio_task = asyncio.create_task(_run_task(handle))
    return task.id


async def _run_task(handle: TaskHandle) -> None:
    """Drive a flow to completion against `handle`.

    Translates exit modes into terminal task statuses:

    - normal return → `completed` with serialized result
    - `PrompterCancelledError` → `cancelled`
    - any other `Exception` → `failed` with `error=str(exc)`
    - serializer failure → `failed` (the flow finished but we couldn't
      shape its result — better to surface that than dump a partial)
    """
    handle.set_started(time.time())
    prompter = TaskPrompter(handle)
    sink = TaskSink(handle)
    try:
        flow_fn, serializer = _select_flow(handle.task.kind)
    except ValueError as exc:
        handle.set_failed(str(exc), time.time())
        return

    def _runner() -> Any:
        with bind_sink(sink):
            return flow_fn(handle.task.params, prompter)

    try:
        result = await asyncio.to_thread(_runner)
    except PrompterCancelledError:
        handle.set_cancelled(time.time())
        return
    except Exception as exc:
        logger.exception("task %s failed", handle.task.id)
        handle.set_failed(str(exc), time.time())
        return

    try:
        serialized = serializer(result)
    except Exception as exc:
        logger.exception("task %s result serialization failed", handle.task.id)
        handle.set_failed(f"result serialization failed: {exc}", time.time())
        return

    handle.set_completed(serialized, time.time())
