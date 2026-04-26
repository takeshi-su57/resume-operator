"""`POST /api/score` — wrap the [score CLI command](src/resume_operator/main.py).

Accepts absolute or project-relative paths to a master YAML (or legacy
resume PDF) and a job description text file. Runs `build_score_graph`
and returns the resulting `ATSScore`. No interactive state — plain
request/response.

Since the server runs on localhost, file paths are the natural contract
(matching how the Tauri shell acquires them via the OS file dialog).
Multipart uploads are avoidable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from resume_operator.graph import build_score_graph
from resume_operator.state import ATSScore

router = APIRouter()


class ScoreRequest(BaseModel):
    master: str | None = None  # path to master_resume.yaml
    resume: str | None = None  # path to resume PDF (legacy)
    job: str  # path to job description text file

    @model_validator(mode="after")
    def _exactly_one_source(self) -> ScoreRequest:
        if not self.master and not self.resume:
            raise ValueError("provide either `master` or `resume`")
        if self.master and self.resume:
            raise ValueError("provide `master` or `resume`, not both")
        return self


class ScoreResponse(BaseModel):
    ats_score: ATSScore
    errors: list[str]


def _validate_paths(req: ScoreRequest) -> None:
    for label, value in (("master", req.master), ("resume", req.resume), ("job", req.job)):
        if value is None:
            continue
        p = Path(value)
        if not p.exists() or not p.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"{label} path does not exist or is not a file: {value}",
            )


@router.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    _validate_paths(req)

    initial: dict[str, Any] = {"job_description_path": req.job}
    if req.master:
        initial["master_path"] = req.master
    else:
        initial["resume_path"] = req.resume

    result = build_score_graph().invoke(initial)
    ats = result.get("ats_score") or ATSScore()
    if not isinstance(ats, ATSScore):
        ats = ATSScore.model_validate(ats)
    return ScoreResponse(ats_score=ats, errors=list(result.get("errors", [])))
