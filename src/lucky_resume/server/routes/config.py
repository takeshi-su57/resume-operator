"""`GET / PATCH /api/config` — user-scoped JSON config alongside ``.env``.

Used today by the GUI's run-history persistence: Bootstrap and Extract
Style push the (source, output, at) tuple of every successful run into
``config.json`` so the lists survive an app reinstall — localStorage was
the prior backing store and got blown away on every webview profile
reset.

Schema is owned by the frontend: the route is a thin pass-through that
deep-merges PATCH bodies into the file. Adding a new persistent surface
just means picking a top-level key and writing it; no schema migration
on the server side.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lucky_resume.tools.user_config import (
    config_file_path,
    read_config,
    write_config,
)

router = APIRouter()


class UserConfigResponse(BaseModel):
    """Wraps the raw config plus its resolved on-disk path so the GUI
    can show "stored at ..." in the same way it shows the env file
    path."""

    config: dict[str, Any] = Field(default_factory=dict)
    config_file_path: str


class UserConfigPatch(BaseModel):
    """PATCH body — accepts arbitrary partial config. Validated only as
    "must be an object"; per-key shape is enforced by the frontend
    schemas."""

    # Pydantic strips unknown fields by default; using a single `data`
    # field keeps the body explicit and avoids polluting the model with
    # every possible top-level key.
    data: dict[str, Any] = Field(default_factory=dict)


@router.get("/config", response_model=UserConfigResponse)
def read_user_config() -> UserConfigResponse:
    return UserConfigResponse(
        config=read_config(),
        config_file_path=str(config_file_path()),
    )


@router.patch("/config", response_model=UserConfigResponse)
def patch_user_config(payload: UserConfigPatch) -> UserConfigResponse:
    merged = write_config(payload.data)
    return UserConfigResponse(
        config=merged,
        config_file_path=str(config_file_path()),
    )
