"""`POST /api/parse-resume` — wrap the [parse-resume CLI command](src/resume_operator/main.py).

PDF in (by path), `ResumeData` out. No interactive state. Calls the
`parse_resume` node directly — no graph needed, matching the CLI's
behavior."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from resume_operator.nodes.parse_resume import parse_resume as parse_resume_node
from resume_operator.state import ResumeData, ResumeOptimizerState

router = APIRouter()


class ParseResumeRequest(BaseModel):
    resume: str  # path to resume PDF


class ParseResumeResponse(BaseModel):
    resume: ResumeData
    errors: list[str]


@router.post("/parse-resume", response_model=ParseResumeResponse)
def parse_resume(req: ParseResumeRequest) -> ParseResumeResponse:
    p = Path(req.resume)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=400, detail=f"resume path not found: {req.resume}")
    if p.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="resume must be a .pdf file")

    state = ResumeOptimizerState(resume_path=str(p))
    result = parse_resume_node(state)
    resume_obj = result.get("resume") or ResumeData()
    if not isinstance(resume_obj, ResumeData):
        resume_obj = ResumeData.model_validate(resume_obj)
    return ParseResumeResponse(
        resume=resume_obj,
        errors=list(result.get("errors", [])),
    )
