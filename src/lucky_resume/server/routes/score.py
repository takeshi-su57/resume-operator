"""`POST /api/score` — wrap the [score CLI command](src/lucky_resume/main.py).

Accepts absolute or project-relative paths to a master YAML (or legacy
resume PDF) and a job description text file. Runs `build_score_graph`
and returns the resulting `ATSScore`. No interactive state — plain
request/response.

Since the server runs on localhost, file paths are the natural contract
(matching how the Tauri shell acquires them via the OS file dialog).
Multipart uploads are avoidable.

Alongside the ATS report, the response carries a slim `MasterView`
echoing the loaded master content (contact values, summary, experience,
education, skills). The frontend uses it to expand the Score dashboard's
structural rows from "present / missing" booleans into the actual data,
so Bruno can read the resume the score was computed against without
a second trip through the file picker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from lucky_resume.graph import build_score_graph
from lucky_resume.state import (
    ATSScore,
    EducationEntry,
    ExperienceEntry,
    Link,
    ResumeData,
    ResumeMaster,
    SkillGroup,
)

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


class MasterView(BaseModel):
    """Read-only summary of the resume content the score was computed against.

    Mirrors the most-asked-for fields when reviewing a score: contact
    details, the actual summary text, and the full experience / education
    / skills lists. Skipping `certifications` and the raw text — neither
    appears on the Score dashboard today and adding them would balloon the
    response."""

    name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[Link] = Field(default_factory=list)
    summary: str = ""
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skill_groups: list[SkillGroup] = Field(default_factory=list)


class ScoreResponse(BaseModel):
    ats_score: ATSScore
    errors: list[str]
    # Optional so legacy PDF inputs still parse cleanly when the master
    # isn't loaded — the dashboard hides expanded details when missing.
    master_view: MasterView | None = None


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


def _master_to_view(master: ResumeMaster) -> MasterView:
    return MasterView(
        name=master.name,
        headline=master.headline,
        email=master.email,
        phone=master.phone,
        location=master.location,
        links=list(master.links),
        summary=master.summary,
        experience=list(master.experience),
        education=list(master.education),
        skills=list(master.skills),
        skill_groups=list(master.skill_groups),
    )


def _resume_to_view(resume: ResumeData) -> MasterView:
    """Best-effort projection of the legacy `ResumeData` shape onto `MasterView`.

    `parse_resume` returns loosely structured experience/education dicts that
    don't carry IDs — we synthesize sequential ones so the frontend keys
    don't collide. Bullets aren't separated in the legacy parse, so the
    `bullets` array is left empty and the role/company surface in the row
    header alone."""

    experience: list[ExperienceEntry] = []
    for idx, entry in enumerate(resume.experience):
        experience.append(
            ExperienceEntry(
                id=f"exp-{idx + 1}",
                role=str(entry.get("role", "")),
                company=str(entry.get("company", "")),
                start_date=str(entry.get("start_date", "")),
                end_date=str(entry.get("end_date", "")),
            )
        )
    education: list[EducationEntry] = []
    for idx, entry in enumerate(resume.education):
        education.append(
            EducationEntry(
                id=f"edu-{idx + 1}",
                degree=str(entry.get("degree", "")),
                school=str(entry.get("school", "")),
                start_date=str(entry.get("start_date", "")),
                end_date=str(entry.get("end_date", "")),
            )
        )
    return MasterView(
        name=resume.name,
        email=resume.email,
        phone=resume.phone,
        summary=resume.summary,
        experience=experience,
        education=education,
        skills=list(resume.skills),
    )


def _build_master_view(result: dict[str, Any]) -> MasterView | None:
    master = result.get("master")
    if isinstance(master, ResumeMaster):
        return _master_to_view(master)
    if isinstance(master, dict):
        return _master_to_view(ResumeMaster.model_validate(master))
    resume = result.get("resume")
    if isinstance(resume, ResumeData):
        return _resume_to_view(resume)
    if isinstance(resume, dict):
        return _resume_to_view(ResumeData.model_validate(resume))
    return None


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
    return ScoreResponse(
        ats_score=ats,
        errors=list(result.get("errors", [])),
        master_view=_build_master_view(result),
    )
