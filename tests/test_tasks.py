"""Task registry + runner end-to-end tests.

Drives `start_task()` directly against an asyncio loop (no
`fastapi.testclient.TestClient` in the loop), since `TestClient` doesn't
reliably progress `asyncio.create_task`-spawned background work between
its blocking sync HTTP calls. The implementation works correctly in
production (the Tauri sidecar runs uvicorn with a long-lived loop); the
tests just need a harness that mirrors that.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from lucky_resume.server.tasks import storage
from lucky_resume.server.tasks.lifecycle import reconcile_on_startup
from lucky_resume.server.tasks.model import Task, new_task_id
from lucky_resume.server.tasks.registry import get_registry
from lucky_resume.server.tasks.runner import start_task
from lucky_resume.state import (
    ATSScore,
    ResumeMaster,
    TailoredItem,
    TailoredResume,
)


@pytest.fixture(autouse=True)
def _isolate_app_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Park task storage under tmp_path so tests don't touch real %APPDATA%."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("RESUME_OPERATOR_ENV_FILE", str(tmp_path / ".env"))
    for handle in list(get_registry().all()):
        get_registry().drop(handle.task.id)


async def _wait_for_terminal(task_id: str, timeout_s: float = 5.0) -> Task:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        handle = get_registry().get(task_id)
        if handle is not None and handle.is_terminal():
            return handle.task
        await asyncio.sleep(0.05)
    pytest.fail(f"task {task_id} didn't reach a terminal status within {timeout_s}s")


# ---------------------------------------------------------------------------
# new_task_id
# ---------------------------------------------------------------------------


class TestNewTaskId:
    def test_ids_are_sortable_by_creation_time(self) -> None:
        # Compare by the timestamp prefix only — within the same millisecond
        # the random suffix is intentionally not ordered.
        a = new_task_id()
        b = new_task_id()
        assert a.split("-")[0] <= b.split("-")[0]

    def test_ids_are_unique(self) -> None:
        ids = {new_task_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# Score lifecycle — start_task → completed
# ---------------------------------------------------------------------------


class TestScoreLifecycle:
    async def test_completes_with_serialized_result(self, tmp_path: Path) -> None:
        master = tmp_path / "m.yaml"
        master.write_text("name: T\n")
        job = tmp_path / "j.txt"
        job.write_text("role")

        with patch("lucky_resume.flows.score_session.build_score_graph") as mock_build:
            graph = MagicMock()
            graph.invoke.return_value = {
                "ats_score": ATSScore(score=0.42, reasoning="meh"),
                "errors": [],
            }
            mock_build.return_value = graph

            task_id = start_task(
                "score", {"master": str(master), "resume": None, "job": str(job)}
            )
            task = await _wait_for_terminal(task_id)

            assert task.status == "completed"
            assert task.error is None
            assert task.result is not None
            assert task.result["ats_score"]["score"] == pytest.approx(0.42)
            graph.invoke.assert_called_once()

    async def test_invalid_paths_land_in_failed(self, tmp_path: Path) -> None:
        task_id = start_task(
            "score", {"master": "nope.yaml", "resume": None, "job": "missing.txt"}
        )
        task = await _wait_for_terminal(task_id)
        assert task.status == "failed"
        assert task.error and "does not exist" in task.error


# ---------------------------------------------------------------------------
# Run lifecycle — answer the first approval prompt to drive to completion
# ---------------------------------------------------------------------------


class TestRunLifecycle:
    async def test_approval_loop_accepts(self, tmp_path: Path) -> None:
        master = tmp_path / "m.yaml"
        master.write_text("name: X\n")
        job = tmp_path / "j.txt"
        job.write_text("role")

        tailor_result: dict[str, Any] = {
            "ats_score": ATSScore(score=0.9, reasoning=""),
            "tailored_resume": TailoredResume(
                items=[TailoredItem(source_id="master:exp-1-b1", action="keep")]
            ),
            "master": ResumeMaster(name="X"),
            "errors": [],
        }

        with (
            patch("lucky_resume.flows.run_session.build_tailor_graph") as mock_tailor,
            patch("lucky_resume.flows.run_session.build_finalize_graph") as mock_finalize,
        ):
            tailor = MagicMock()
            tailor.invoke.return_value = tailor_result
            mock_tailor.return_value = tailor

            finalize = MagicMock()
            finalize.invoke.return_value = {**tailor_result, "output_path": "out.pdf"}
            mock_finalize.return_value = finalize

            task_id = start_task(
                "run",
                {
                    "master": str(master),
                    "resume": None,
                    "job": str(job),
                    "no_enrich": True,
                    "no_approve": False,
                    "max_iter": 3,
                    "facts": None,
                    "output": None,
                    "style": None,
                },
            )

            # Wait until the task parks on a confirm prompt.
            handle = get_registry().get(task_id)
            assert handle is not None
            for _ in range(100):
                await asyncio.sleep(0.05)
                if handle.task.pending_prompt is not None:
                    break
            else:
                pytest.fail("task never reached a pending prompt")

            seq = handle.task.pending_prompt.prompt_seq
            assert handle.deposit_reply(seq, True)

            task = await _wait_for_terminal(task_id)
            assert task.status == "completed", f"error={task.error}"


# ---------------------------------------------------------------------------
# Lifecycle scan — non-terminal tasks on disk become `interrupted`
# ---------------------------------------------------------------------------


class TestStartupReconciliation:
    def test_running_task_marked_interrupted(self, tmp_path: Path) -> None:
        # Pre-seed a "running" task on disk as if a previous sidecar process
        # crashed. Reconcile should flip it to `interrupted`.
        task = Task(id=new_task_id(), kind="run", status="running")
        storage.save(task)

        reconcile_on_startup()

        loaded = storage.load(task.id)
        assert loaded is not None
        assert loaded.status == "interrupted"
        assert loaded.error and "restarted" in loaded.error.lower()

    def test_terminal_task_left_alone(self, tmp_path: Path) -> None:
        task = Task(id=new_task_id(), kind="score", status="completed")
        storage.save(task)

        reconcile_on_startup()

        loaded = storage.load(task.id)
        assert loaded is not None
        assert loaded.status == "completed"


# ---------------------------------------------------------------------------
# Cancel — request_cancel raises PrompterCancelledError inside a parked prompt
# ---------------------------------------------------------------------------


class TestCancel:
    async def test_cancel_during_prompt_unwinds_to_cancelled(
        self, tmp_path: Path
    ) -> None:
        master = tmp_path / "m.yaml"
        master.write_text("name: X\n")
        job = tmp_path / "j.txt"
        job.write_text("role")

        tailor_result: dict[str, Any] = {
            "ats_score": ATSScore(score=0.9, reasoning=""),
            "tailored_resume": TailoredResume(
                items=[TailoredItem(source_id="master:exp-1-b1", action="keep")]
            ),
            "master": ResumeMaster(name="X"),
            "errors": [],
        }
        with (
            patch("lucky_resume.flows.run_session.build_tailor_graph") as mock_tailor,
            patch("lucky_resume.flows.run_session.build_finalize_graph") as mock_finalize,
        ):
            tailor = MagicMock()
            tailor.invoke.return_value = tailor_result
            mock_tailor.return_value = tailor
            finalize = MagicMock()
            finalize.invoke.return_value = tailor_result
            mock_finalize.return_value = finalize

            task_id = start_task(
                "run",
                {
                    "master": str(master),
                    "resume": None,
                    "job": str(job),
                    "no_enrich": True,
                    "no_approve": False,
                    "max_iter": 3,
                    "facts": None,
                    "output": None,
                    "style": None,
                },
            )
            handle = get_registry().get(task_id)
            assert handle is not None

            # Wait until the task parks on a prompt, then cancel.
            for _ in range(100):
                await asyncio.sleep(0.05)
                if handle.task.pending_prompt is not None:
                    break
            handle.request_cancel()

            task = await _wait_for_terminal(task_id)
            assert task.status == "cancelled"
