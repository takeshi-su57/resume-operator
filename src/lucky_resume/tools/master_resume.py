"""Master resume YAML I/O and conversions."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from lucky_resume.state import (
    EducationEntry,
    ExperienceBullet,
    ExperienceEntry,
    ResumeData,
    ResumeMaster,
)

logger = logging.getLogger(__name__)


class MasterResumeError(ValueError):
    """Raised when the master resume YAML is missing or malformed."""


def load_master(path: Path) -> ResumeMaster:
    """Load and validate a `master_resume.yaml` file.

    Raises `MasterResumeError` if the file is missing or fails schema validation.
    """
    if not path.exists():
        raise MasterResumeError(f"master resume not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MasterResumeError(f"master resume YAML parse error: {exc}") from exc
    if raw is None:
        raise MasterResumeError(f"master resume is empty: {path}")
    if not isinstance(raw, dict):
        raise MasterResumeError(
            f"master resume must be a mapping at the top level, got {type(raw).__name__}"
        )
    try:
        master = ResumeMaster.model_validate(raw)
    except Exception as exc:
        raise MasterResumeError(f"master resume schema validation failed: {exc}") from exc
    logger.info(
        "load_master: loaded %s — experience=%d, education=%d, skills=%d",
        path,
        len(master.experience),
        len(master.education),
        len(master.skills),
    )
    return master


def save_master(master: ResumeMaster, path: Path) -> None:
    """Serialize a `ResumeMaster` to YAML. Creates parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = master.model_dump()
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    logger.info("save_master: wrote %s", path)


def resume_data_to_master(resume: ResumeData) -> ResumeMaster:
    """Convert the legacy LLM-parsed `ResumeData` into a `ResumeMaster` with stable IDs.

    Used by the `bootstrap` command to seed a YAML file from an existing PDF.
    """
    experience = [
        _experience_entry_from_dict(idx, entry) for idx, entry in enumerate(resume.experience)
    ]
    education = [
        _education_entry_from_dict(idx, entry) for idx, entry in enumerate(resume.education)
    ]
    return ResumeMaster(
        name=resume.name,
        email=resume.email,
        phone=resume.phone,
        summary=resume.summary,
        experience=experience,
        education=education,
        skills=list(resume.skills),
        certifications=list(resume.certifications),
    )


def _experience_entry_from_dict(idx: int, entry: dict[str, Any]) -> ExperienceEntry:
    role_id = f"exp-{idx + 1}"
    bullets_raw = entry.get("bullets") or entry.get("description") or ""
    bullets = _parse_bullets(role_id, bullets_raw)
    return ExperienceEntry(
        id=role_id,
        role=str(entry.get("role") or entry.get("title") or ""),
        company=str(entry.get("company") or ""),
        location=str(entry.get("location") or ""),
        start_date=str(entry.get("start_date") or entry.get("start") or ""),
        end_date=str(entry.get("end_date") or entry.get("end") or ""),
        bullets=bullets,
    )


def _parse_bullets(role_id: str, raw: Any) -> list[ExperienceBullet]:
    if isinstance(raw, list):
        texts = [str(item).strip() for item in raw if str(item).strip()]
    elif isinstance(raw, str):
        texts = [line.lstrip("-*• ").strip() for line in raw.splitlines() if line.strip()]
    else:
        texts = []
    return [ExperienceBullet(id=f"{role_id}-b{i + 1}", text=text) for i, text in enumerate(texts)]


def _education_entry_from_dict(idx: int, entry: dict[str, Any]) -> EducationEntry:
    return EducationEntry(
        id=f"edu-{idx + 1}",
        degree=str(entry.get("degree") or ""),
        school=str(entry.get("school") or entry.get("institution") or ""),
        location=str(entry.get("location") or ""),
        start_date=str(entry.get("start_date") or entry.get("start") or ""),
        end_date=str(entry.get("end_date") or entry.get("end") or ""),
        details=str(entry.get("details") or ""),
    )
