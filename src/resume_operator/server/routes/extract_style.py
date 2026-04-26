"""`POST /api/extract-style` — wrap the [extract-style CLI command](src/resume_operator/main.py).

.docx in (by path), `StyleTemplate` out. No interactive state. Thin
wrapper around `extract_style_from_docx` (#72) — same logic the CLI's
`extract-style` command uses."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from resume_operator.tools.style import StyleTemplate, save_style
from resume_operator.tools.style_from_docx import (
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
