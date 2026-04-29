"""`GET /api/yaml?path=...` — read + parse a YAML file for the GUI tree preview.

The desktop app uses this to show the contents of a master YAML, a
facts bank, or a style template in the `<YamlTree>` component without
opening it in a separate editor. The endpoint is read-only; writes go
through the dedicated routes (`save_master`, `save_style`, ...).

Security note: this is a localhost-only sidecar exposed to the bundled
Tauri webview. The Tauri capability list pins shell access; the sidecar
itself doesn't need to enforce a directory whitelist beyond rejecting
paths that don't exist or aren't files. The frontend never sends a path
the user hasn't already touched via a file dialog.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from lucky_resume.tools.builtin_styles import (
    is_builtin_identifier,
    resolve_style_source,
)

router = APIRouter()


class YamlPreviewResponse(BaseModel):
    """Round-tripped path + parsed content. The path is normalised so
    the GUI's history can dedupe across slash variants without a second
    `Path.resolve()` round-trip."""

    path: str
    content: dict[str, Any] | list[Any] | str | int | float | bool | None


@router.get("/yaml", response_model=YamlPreviewResponse)
def read_yaml(
    path: str = Query(
        ..., description="Absolute or cwd-relative path to a YAML file."
    ),
) -> YamlPreviewResponse:
    # `builtin:<name>` resolves to a temp file that mirrors the bundled
    # YAML — same flow the rest of the pipeline uses, so the preview
    # matches what `--style builtin:default` would render with.
    if is_builtin_identifier(path):
        try:
            p = resolve_style_source(path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    if p.suffix.lower() not in {".yaml", ".yml"}:
        raise HTTPException(status_code=400, detail="path must be a .yaml / .yml file")
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"read error: {exc}") from exc
    try:
        content = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=422, detail=f"yaml parse error: {exc}") from exc
    return YamlPreviewResponse(path=str(p.resolve()), content=content)
