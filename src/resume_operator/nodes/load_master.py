"""Node: Load the hand-maintained master resume YAML (no LLM)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from resume_operator.events import node_span
from resume_operator.state import (
    JobDescription,
    ResumeData,
    ResumeMaster,
    ResumeOptimizerState,
)
from resume_operator.tools.facts_bank import FactsBankError, load_facts
from resume_operator.tools.master_resume import MasterResumeError, load_master

logger = logging.getLogger(__name__)


def load_master_node(state: ResumeOptimizerState) -> dict[str, Any]:
    """Read `master_resume.yaml` into `state.master`.

    Also populates `state.resume` from the master so downstream nodes that
    still consume `ResumeData` (ats_score, analyze_gaps, optimize_content)
    keep working until their migration in #026.
    """
    with node_span("load_master"):
        return _load_master_body(state)


def _load_master_body(state: ResumeOptimizerState) -> dict[str, Any]:
    logger.info("load_master: starting")
    errors: list[str] = list(state.errors)
    result: dict[str, Any] = {}

    if not state.master_path:
        logger.error("load_master: master_path is empty")
        errors.append("load_master: master_path is empty")
        return {"errors": errors}

    try:
        master = load_master(Path(state.master_path))
    except MasterResumeError as exc:
        logger.error("load_master: %s", exc)
        errors.append(f"load_master: {exc}")
        return {"errors": errors}

    result["master"] = master
    result["resume"] = _master_to_resume_data(master)

    # --- Optional facts bank ---
    facts_path = Path(state.facts_path) if state.facts_path else None
    try:
        facts = load_facts(facts_path)
    except FactsBankError as exc:
        logger.error("load_master: %s", exc)
        errors.append(f"load_master: {exc}")
        return {"errors": errors}
    result["facts"] = facts

    # Read job description (same contract as the legacy parse_resume node).
    job_raw_text = state.job_description_text
    if not job_raw_text and state.job_description_path:
        try:
            job_raw_text = Path(state.job_description_path).read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("load_master: failed to read job description: %s", exc)
            errors.append(f"load_master: failed to read job description: {exc}")

    if job_raw_text:
        result["job_description"] = JobDescription(raw_text=job_raw_text)

    logger.info(
        "load_master: completed — experience=%d, education=%d, skills=%d",
        len(master.experience),
        len(master.education),
        len(master.skills),
    )

    if errors != list(state.errors):
        result["errors"] = errors
    return result


def _master_to_resume_data(master: ResumeMaster) -> ResumeData:
    """Flatten `ResumeMaster` into the legacy `ResumeData` shape for downstream compatibility."""
    experience = [
        {
            "role": entry.role,
            "company": entry.company,
            "start_date": entry.start_date,
            "end_date": entry.end_date,
            "description": "\n".join(f"- {b.text}" for b in entry.bullets),
        }
        for entry in master.experience
    ]
    education = [
        {
            "degree": entry.degree,
            "school": entry.school,
            "start_date": entry.start_date,
            "end_date": entry.end_date,
            "details": entry.details,
        }
        for entry in master.education
    ]
    return ResumeData(
        name=master.name,
        email=master.email,
        phone=master.phone,
        summary=master.summary,
        experience=experience,
        education=education,
        skills=list(master.skills),
        certifications=list(master.certifications),
        raw_text=_render_master_as_text(master),
    )


def _render_master_as_text(master: ResumeMaster) -> str:
    """Plain-text rendering of the master resume, used as the `raw_text` downstream nodes see."""
    lines: list[str] = []
    if master.name:
        lines.append(master.name)
    contact = " | ".join(x for x in [master.email, master.phone, master.location] if x)
    if contact:
        lines.append(contact)
    if master.summary:
        lines.extend(["", "SUMMARY", master.summary])
    if master.experience:
        lines.extend(["", "EXPERIENCE"])
        for e in master.experience:
            header_parts = [e.role, e.company]
            dates = " – ".join(x for x in [e.start_date, e.end_date] if x)
            if dates:
                header_parts.append(dates)
            lines.append(" | ".join(p for p in header_parts if p))
            lines.extend(f"- {b.text}" for b in e.bullets)
    if master.education:
        lines.extend(["", "EDUCATION"])
        for ed in master.education:
            lines.append(" | ".join(p for p in [ed.degree, ed.school] if p))
            if ed.details:
                lines.append(ed.details)
    if master.skills:
        lines.extend(["", "SKILLS", ", ".join(master.skills)])
    if master.certifications:
        lines.extend(["", "CERTIFICATIONS"])
        lines.extend(f"- {c}" for c in master.certifications)
    return "\n".join(lines)
