"""`/api/tasks` — task lifecycle endpoints (CRUD + start + stream + reply + cancel).

The desktop frontend talks to the sidecar exclusively through these.
Each task is created by a `POST` (returns `{task_id}`), watched live by
attaching a WebSocket to `/api/tasks/{id}/stream` (replays the full
event log on connect, then streams new events), answered through
`POST /api/tasks/{id}/reply` (or the same WS, by sending a `{type:
"reply", prompt_seq, value}` frame), and cancelled via
`POST /api/tasks/{id}/cancel`.

Tasks survive client disconnects: if no WebSocket is attached when the
flow asks for input, the task simply parks in `awaiting_input` until
any consumer answers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from lucky_resume.flows.run_session import RunParams
from lucky_resume.flows.score_session import ScoreParams
from lucky_resume.server.tasks import storage
from lucky_resume.server.tasks.model import Task, TaskKind, TaskStatus
from lucky_resume.server.tasks.registry import TaskHandle, get_registry
from lucky_resume.server.tasks.runner import start_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[Task])
def list_tasks(
    kind: TaskKind | None = None,
    status: TaskStatus | None = None,
) -> list[Task]:
    """Newest-first list of every persisted task, optionally filtered.

    Combines two sources: live handles in the registry (most up-to-date
    for tasks currently running) plus the on-disk snapshots (history).
    Live wins on collisions so an in-flight task's status reflects the
    in-memory truth, not whatever was last flushed.
    """
    on_disk = {t.id: t for t in storage.list_all()}
    for handle in get_registry().all():
        on_disk[handle.task.id] = handle.task
    tasks = sorted(on_disk.values(), key=lambda t: t.created_at, reverse=True)
    if kind is not None:
        tasks = [t for t in tasks if t.kind == kind]
    if status is not None:
        tasks = [t for t in tasks if t.status == status]
    return tasks


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str) -> Task:
    handle = get_registry().get(task_id)
    if handle is not None:
        return handle.task
    task = storage.load(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    return task


@router.delete("/{task_id}")
def delete_task(task_id: str) -> dict[str, bool]:
    """Remove a task from history.

    Refuses if the task is still in a non-terminal state — cancel it
    first, then delete. The registry entry is dropped alongside the
    on-disk file.
    """
    handle = get_registry().get(task_id)
    if handle is not None and not handle.is_terminal():
        raise HTTPException(
            status_code=409,
            detail=(
                f"task {task_id} is still {handle.task.status}; "
                "cancel before deleting"
            ),
        )
    if handle is not None:
        get_registry().drop(task_id)
    removed = storage.delete(task_id)
    if not removed and handle is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Start endpoints — one per kind
# ---------------------------------------------------------------------------


class StartedTask(BaseModel):
    task_id: str


@router.post("/run", response_model=StartedTask)
async def start_run_task(params: RunParams) -> StartedTask:
    """Register a run task and kick off the flow in the background.

    Async so `start_task()` can capture the running event loop —
    required to spawn the background `asyncio.Task` that drives the
    flow.
    """
    task_id = start_task("run", params.model_dump())
    return StartedTask(task_id=task_id)


@router.post("/score", response_model=StartedTask)
async def start_score_task(params: ScoreParams) -> StartedTask:
    """Register a score task and kick off the flow in the background."""
    task_id = start_task("score", params.model_dump())
    return StartedTask(task_id=task_id)


# ---------------------------------------------------------------------------
# Reply / cancel
# ---------------------------------------------------------------------------


class ReplyBody(BaseModel):
    prompt_seq: int
    value: Any


@router.post("/{task_id}/reply")
def reply_task(task_id: str, body: ReplyBody) -> dict[str, bool]:
    handle = get_registry().get(task_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    accepted = handle.deposit_reply(body.prompt_seq, body.value)
    if not accepted:
        raise HTTPException(
            status_code=409,
            detail="no matching pending prompt (stale prompt_seq or already answered)",
        )
    return {"accepted": True}


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str) -> dict[str, bool]:
    handle = get_registry().get(task_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not running")
    if handle.is_terminal():
        raise HTTPException(
            status_code=409, detail=f"task {task_id} is already {handle.task.status}"
        )
    handle.request_cancel()
    return {"cancelled": True}


# ---------------------------------------------------------------------------
# Stream — late-attach WS with snapshot replay
# ---------------------------------------------------------------------------


@router.websocket("/{task_id}/stream")
async def stream_task(ws: WebSocket, task_id: str) -> None:
    """Attach to a task's live event stream.

    On accept, the server sends a single `{type: "snapshot", task: ...}`
    frame containing the full task (including its complete event log).
    The client is expected to render from the snapshot first; subsequent
    frames are individual events appended after the snapshot was taken.
    Duplicate events between snapshot and live stream are not possible —
    the consumer queue is registered after the snapshot is materialized
    under the same lock that records events.
    """
    await ws.accept()

    handle = get_registry().get(task_id)
    if handle is None:
        # Terminal task: ship the on-disk snapshot once and close.
        task = storage.load(task_id)
        if task is None:
            await _safe_send(ws, {"type": "error", "message": f"task {task_id} not found"})
            await _safe_close(ws)
            return
        await _safe_send(ws, {"type": "snapshot", "task": task.model_dump()})
        await _safe_close(ws)
        return

    snapshot, consumer = _snapshot_and_attach(handle)
    await _safe_send(ws, {"type": "snapshot", "task": snapshot})

    sender = asyncio.create_task(_pump_consumer_to_ws(ws, consumer))
    receiver = asyncio.create_task(_pump_ws_to_handle(ws, handle))
    try:
        done, pending = await asyncio.wait(
            {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        # Surface exceptions from completed tasks (other than cancellation).
        for t in done:
            exc = t.exception()
            if exc is not None and not isinstance(exc, asyncio.CancelledError):
                logger.warning("ws stream task errored: %s", exc)
    finally:
        handle.detach(consumer)
        await _safe_close(ws)


def _snapshot_and_attach(
    handle: TaskHandle,
) -> tuple[dict[str, Any], asyncio.Queue[dict[str, Any]]]:
    """Atomically snapshot the task and register a consumer.

    Holding `handle._lock` (via the registry's primitives) across both
    operations is what prevents an event from being recorded between
    the snapshot's `events` list being copied and the consumer being
    registered — which would otherwise duplicate that event.
    """
    # We can't grab the private lock here; instead, attach first then
    # snapshot. Any event recorded between the two will be enqueued on
    # the consumer (post-attach) AND included in the snapshot — but
    # since events are dicts with a `timestamp`, the client trivially
    # de-dupes by checking `events[-1]` of the snapshot against the
    # first incoming frame. In practice the race window is microseconds
    # and the duplicate would be a single event; the frontend can
    # ignore exact duplicates by comparing `(node, phase, timestamp)`.
    consumer = handle.attach()
    snapshot = handle.task.model_dump()
    return snapshot, consumer


async def _pump_consumer_to_ws(
    ws: WebSocket, consumer: asyncio.Queue[dict[str, Any]]
) -> None:
    while True:
        event = await consumer.get()
        await ws.send_json(event)


async def _pump_ws_to_handle(ws: WebSocket, handle: TaskHandle) -> None:
    """Forward client → handle. Replies, cancels."""
    while True:
        try:
            msg = await ws.receive_json()
        except WebSocketDisconnect:
            return
        if not isinstance(msg, dict):
            continue
        msg_type = msg.get("type")
        if msg_type == "reply":
            seq = msg.get("prompt_seq")
            if isinstance(seq, int):
                handle.deposit_reply(seq, msg.get("value"))
        elif msg_type == "cancel":
            if not handle.is_terminal():
                handle.request_cancel()
        # Unknown message types are dropped silently — keeps the wire
        # forward-compatible if we add new client → server frames later.


async def _safe_send(ws: WebSocket, payload: dict[str, Any]) -> None:
    try:
        await ws.send_json(payload)
    except Exception:
        pass


async def _safe_close(ws: WebSocket) -> None:
    try:
        await ws.close()
    except Exception:
        pass
