"""Helpers that bridge a FastAPI WebSocket to a blocking interactive flow.

The flows (`flows.approval.run_approval_loop`, the bootstrap interview,
etc.) are blocking — they call `Prompter` methods that wait for user
input. `run_flow_over_ws` sets up the plumbing:

1. Accepts the WebSocket and reads a single `{"type": "start", ...}`
   message carrying the flow params.
2. Creates a `WebSocketPrompter` + `WebSocketEventSink` bound to this
   connection.
3. Spawns the sync `flow_fn(params, prompter)` in a background thread
   so the event loop is free to pump WS messages.
4. Forwards every `{"type": "reply", ...}` from the client into the
   prompter's inbox; drops any other client messages.
5. Awaits flow completion; sends `{"type": "done", "result": ...}`
   (or `{"type": "error", ...}`) and closes the socket.

Clean disconnects (client closes mid-flow) raise `PrompterDisconnectedError`
inside the worker thread so the flow can return early instead of
deadlocking on an unanswered prompt.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from resume_operator.events import bind_sink
from resume_operator.server.ws_prompter import (
    PrompterDisconnectedError,
    WebSocketEventSink,
    WebSocketPrompter,
)

logger = logging.getLogger(__name__)

FlowFn = Callable[[dict[str, Any], WebSocketPrompter], Any]
ResultSerializer = Callable[[Any], Any]


async def run_flow_over_ws(
    ws: WebSocket,
    *,
    flow_fn: FlowFn,
    serialize_result: ResultSerializer = lambda r: r,
) -> None:
    """Pump a WebSocket against a blocking `flow_fn(params, prompter)`.

    The flow runs in a thread via `asyncio.to_thread`; this coroutine
    handles the WS message pump until the flow finishes or the client
    disconnects.
    """
    await ws.accept()
    loop = asyncio.get_running_loop()
    prompter = WebSocketPrompter(ws, loop)
    sink = WebSocketEventSink(prompter)

    # Consume the opening `start` message.
    try:
        start_msg = await ws.receive_json()
    except WebSocketDisconnect:
        return

    if not isinstance(start_msg, dict) or start_msg.get("type") != "start":
        await ws.send_json({"type": "error", "message": "expected first message with type=start"})
        await ws.close()
        return
    params = start_msg.get("params") or {}

    flow_task = asyncio.create_task(_run_flow(flow_fn, params, prompter, sink))
    pump_task = asyncio.create_task(_pump_client_replies(ws, prompter, flow_task))

    # Wait for the flow to finish (or error). `_pump_client_replies` keeps
    # depositing replies until the flow completes; we cancel it here.
    try:
        result = await flow_task
    except PrompterDisconnectedError:
        pump_task.cancel()
        return
    except Exception as exc:
        logger.exception("flow failed")
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    else:
        try:
            await ws.send_json({"type": "done", "result": serialize_result(result)})
        except Exception:
            pass
    finally:
        pump_task.cancel()
        try:
            await ws.close()
        except Exception:
            pass


async def _run_flow(
    flow_fn: FlowFn,
    params: dict[str, Any],
    prompter: WebSocketPrompter,
    sink: WebSocketEventSink,
) -> Any:
    def _runner() -> Any:
        with bind_sink(sink):
            return flow_fn(params, prompter)

    return await asyncio.to_thread(_runner)


async def _pump_client_replies(
    ws: WebSocket,
    prompter: WebSocketPrompter,
    flow_task: Awaitable[Any],
) -> None:
    """Forward client → prompter. Exits when the flow task completes or
    the client disconnects."""
    try:
        while True:
            msg = await ws.receive_json()
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "reply":
                prompter.deposit_reply(msg)
            # Other message types (heartbeats, cancellations) are accepted
            # but not routed in Phase 1. Add dispatch here as needs grow.
    except WebSocketDisconnect:
        prompter.close()
    except asyncio.CancelledError:
        raise
    except Exception:
        prompter.close()
