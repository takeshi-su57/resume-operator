"""Score-session flow — wraps `build_score_graph` for the task runner.

Same business logic as the (now-deleted) `POST /api/score` route, but
shaped to fit the `(params, prompter) -> dict` contract the task runner
expects. The score graph is non-interactive — it doesn't call any
prompter methods that block on user input — but we still drape a
`prompter.status(...)` around the invocation so the event log carries a
visible "Computing ATS score..." span clients can render while waiting.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from lucky_resume.graph import build_score_graph
from lucky_resume.prompter import Prompter
from lucky_resume.state import (
    ATSScore,
    EducationEntry,
    ExperienceEntry,
    Link,
    ResumeData,
    ResumeMaster,
    SkillGroup,
)

logger = logging.getLogger(__name__)


class ScoreParams(BaseModel):
    """Identical shape to the legacy `ScoreRequest`."""

    master: str | None = None
    resume: str | None = None
    job: str

    @model_validator(mode="after")
    def _exactly_one_source(self) -> ScoreParams:
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


class ScoreResult(BaseModel):
    ats_score: ATSScore
    errors: list[str]
    master_view: MasterView | None = None


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


def _validate_paths(params: ScoreParams) -> None:
    for label, value in (
        ("master", params.master),
        ("resume", params.resume),
        ("job", params.job),
    ):
        if value is None:
            continue
        p = Path(value)
        if not p.exists() or not p.is_file():
            raise ValueError(f"{label} path does not exist or is not a file: {value}")


def execute_score(raw_params: dict[str, Any], prompter: Prompter) -> dict[str, Any]:
    """Run the score graph against `raw_params`. Runs in a background thread."""
    params = ScoreParams.model_validate(raw_params)
    _validate_paths(params)

    initial: dict[str, Any] = {"job_description_path": params.job}
    if params.master:
        initial["master_path"] = params.master
    else:
        initial["resume_path"] = params.resume

    with prompter.status("Computing ATS score..."):
        return build_score_graph().invoke(initial)


def serialize_score_result(result: dict[str, Any]) -> dict[str, Any]:
    """Turn the score graph's loose dict into the `ScoreResult` shape."""
    ats = result.get("ats_score") or ATSScore()
    if not isinstance(ats, ATSScore):
        ats = ATSScore.model_validate(ats)
    payload = ScoreResult(
        ats_score=ats,
        errors=list(result.get("errors", [])),
        master_view=_build_master_view(result),
    )
    return payload.model_dump(exclude_none=False)
