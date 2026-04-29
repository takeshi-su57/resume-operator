"""User-scoped JSON config persisted next to ``.env``.

The ``config.json`` file holds GUI state that survives across launches
but isn't a "setting" in the env-var sense — primarily the recent-runs
history per page. Lives at ``<env_dir>/config.json`` so a single
``%APPDATA%\\lucky-resume`` directory contains everything user-scoped.

Schema is intentionally open-ended: top-level keys grow as new GUI
features need persistence. Today:

```
{
  "history": {
    "bootstrap":     [ {"source": ..., "output": ..., "at": 1234567890}, ... ],
    "extract-style": [ ... ]
  }
}
```

Writes are atomic via the ``write -> rename`` pattern so a crash mid-
write doesn't corrupt prior state. Concurrency: the sidecar runs as a
single-process FastAPI app, so we don't bother with file locks — Python's
GIL + the route handlers' sync nature serialize writes naturally.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from lucky_resume.paths import env_file_path

logger = logging.getLogger(__name__)

# Anything callers can hand us. Mirrors what `json.loads` returns plus
# the `Mapping[str, Any]` we get from request bodies.
JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


def config_file_path() -> Path:
    """Sibling of the runtime ``.env`` file."""
    return env_file_path().parent / "config.json"


def read_config() -> dict[str, Any]:
    """Return the parsed contents of ``config.json``, or ``{}`` when
    the file is missing or empty.

    Malformed JSON is logged and returned as ``{}`` rather than raising —
    a corrupted file shouldn't brick the whole GUI; the next ``write``
    will clobber it with a known-good shape."""

    path = config_file_path()
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("user_config: read failed (%s) — using empty config", exc)
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("user_config: parse failed (%s) — treating as empty", exc)
        return {}
    if not isinstance(data, dict):
        logger.warning(
            "user_config: top-level must be an object, got %s — treating as empty",
            type(data).__name__,
        )
        return {}
    return data


def write_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``updates`` into the on-disk config and return the
    result.

    Object values are recursively merged (sub-keys from ``updates``
    replace matching keys); every other value type — list, scalar,
    None — replaces the existing value wholesale. This matches what
    GUIs typically expect when they PATCH (replace this list, set
    this scalar) without having to worry about array-merge semantics.

    The file is written via a tempfile + ``os.replace`` so a crash
    mid-write leaves the prior file untouched."""

    path = config_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = read_config()
    merged = _deep_merge(current, updates)

    # `delete=False` so we can rename it; tempfile lives on the same
    # filesystem (config dir) so `os.replace` stays atomic.
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=".config.",
        suffix=".tmp",
        delete=False,
    )
    try:
        json.dump(merged, tmp, indent=2, sort_keys=True)
        tmp.flush()
        os.fsync(tmp.fileno())
    finally:
        tmp.close()
    os.replace(tmp.name, path)
    return merged


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dicts; leaf values from `updates` win."""
    out = dict(base)
    for key, value in updates.items():
        if (
            isinstance(value, dict)
            and isinstance(out.get(key), dict)
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out
