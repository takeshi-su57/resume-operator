"""`POST /api/extract-style` — wrap the [extract-style CLI command](src/lucky_resume/main.py).

.docx in (by path), `StyleTemplate` out. No interactive state. Thin
wrapper around `extract_style_from_docx` (#72) — same logic the CLI's
`extract-style` command uses.

Also serves `GET /api/styles/builtin` so the GUI can render chips for
the bundled presets (`default`, `consolas`) without learning where the
package data lives."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lucky_resume.tools.builtin_styles import BuiltinStyle, list_builtin_styles
from lucky_resume.tools.style import StyleTemplate, save_style
from lucky_resume.tools.style_from_docx import (
    StyleExtractionError,
    extract_style_from_docx,
)

router = APIRouter()


class ExtractStyleRequest(BaseModel):
    source: str  # path to reference .docx
    output: str | None = None  # optional path — writes the YAML if provided


class ExtractStyleResponse(BaseModel):
    style: StyleTemplate
    written_to: str | None = None


class BuiltinStylesResponse(BaseModel):
    """Wraps the list so the response is `{styles: [...]}` instead of a bare
    array — leaves room to grow extra metadata (counts, version) without
    breaking clients."""

    styles: list[BuiltinStyle]


@router.post("/extract-style", response_model=ExtractStyleResponse)
def extract_style(req: ExtractStyleRequest) -> ExtractStyleResponse:
    src = Path(req.source)
    if not src.exists() or not src.is_file():
        raise HTTPException(status_code=400, detail=f"source path not found: {req.source}")
    if src.suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="source must be a .docx file")

    try:
        template = extract_style_from_docx(src)
    except StyleExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    written: str | None = None
    if req.output:
        out_path = Path(req.output)
        save_style(template, out_path)
        written = str(out_path)

    return ExtractStyleResponse(style=template, written_to=written)


@router.get("/styles/builtin", response_model=BuiltinStylesResponse)
def builtin_styles() -> BuiltinStylesResponse:
    """Return every preset shipped inside the bundle.

    The frontend uses this to populate the "Built-in" chips on the Run
    and Extract Style screens. Send the resulting `name` back to any
    style-accepting endpoint as `builtin:<name>` and the pipeline
    resolves it via `tools.builtin_styles.resolve_style_source`."""
    return BuiltinStylesResponse(styles=list_builtin_styles())
