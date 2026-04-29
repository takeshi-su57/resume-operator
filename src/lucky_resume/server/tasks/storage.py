"""On-disk persistence for `Task` snapshots.

One JSON file per task at `<tasks_dir>/<id>.json`, written atomically
(tempfile + replace). Listing scans the directory and parses each file —
fine for the user-deletes-only history sizes we expect. If history ever
grows large enough to make scan-on-list slow, swap to an `index.json`
maintained alongside the per-task files.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from lucky_resume.paths import tasks_dir
from lucky_resume.server.tasks.model import Task

logger = logging.getLogger(__name__)


def _task_path(task_id: str) -> Path:
    return tasks_dir() / f"{task_id}.json"


def save(task: Task) -> None:
    """Atomically write `task` to disk.

    Writes to a sibling tempfile then `os.replace`s into place so a
    crash mid-write can't leave a half-written JSON. The whole file is
    rewritten on every save — task records stay small enough that this
    is cheaper than any incremental scheme.
    """
    target = _task_path(task.id)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = task.model_dump_json()
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{task.id}-", suffix=".json.tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, target)
    except Exception:
        # Best effort cleanup; ignore if already gone.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load(task_id: str) -> Task | None:
    """Read a single task from disk, or `None` if missing/corrupt."""
    path = _task_path(task_id)
    if not path.is_file():
        return None
    try:
        return Task.model_validate_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("task %s on disk is unreadable: %s", task_id, exc)
        return None


def delete(task_id: str) -> bool:
    """Remove a task file from disk. Returns False if it didn't exist."""
    path = _task_path(task_id)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def list_all() -> list[Task]:
    """Return every persisted task, newest-first by `created_at`.

    Skips files that fail to parse — a corrupt task shouldn't break the
    list endpoint.
    """
    root = tasks_dir()
    out: list[Task] = []
    if not root.is_dir():
        return out
    for entry in root.iterdir():
        if entry.suffix != ".json" or entry.name.startswith("."):
            continue
        try:
            out.append(Task.model_validate_json(entry.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("skipping unreadable task file %s: %s", entry.name, exc)
    out.sort(key=lambda t: t.created_at, reverse=True)
    return out
