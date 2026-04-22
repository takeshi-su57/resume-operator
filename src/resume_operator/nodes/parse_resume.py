"""Node: Extract structured data from resume PDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.resume_parsing import PARSE_RESUME
from resume_operator.state import (
    EducationEntry,
    ExperienceBullet,
    ExperienceEntry,
    JobDescription,
    Link,
    ResumeData,
    ResumeMaster,
    ResumeOptimizerState,
    SkillGroup,
)
from resume_operator.tools.llm_provider import get_structured_llm
from resume_operator.tools.pdf_parser import extract_text

logger = logging.getLogger(__name__)


class ResumeExperienceLLM(BaseModel):
    role: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    # `bullets` carries every per-role bullet verbatim. The old `description: str`
    # field encouraged the LLM to summarize multiple bullets into one sentence,
    # which defeated the purpose of a structured master resume (see issue #60).
    bullets: list[str] = Field(default_factory=list)
    # Optional per-role tech stack shown as a `Tech: ...` line on well-built
    # senior-engineer resumes (#68). Empty list when the source doesn't show one.
    tech: list[str] = Field(default_factory=list)


class ResumeEducationLLM(BaseModel):
    degree: str = ""
    school: str = ""
    start_date: str = ""
    end_date: str = ""


class ResumeLinkLLM(BaseModel):
    label: str = ""
    url: str = ""


class ResumeSkillGroupLLM(BaseModel):
    category: str = ""
    items: list[str] = Field(default_factory=list)


class ResumeLLMOutput(BaseModel):
    """Schema handed to `with_structured_output` — the LLM fills this in directly.

    Fixed sub-schemas (not raw dicts) so the generated JSON schema is compatible
    with OpenAI's strict mode.
    """

    name: str = ""
    headline: str = ""  # tagline under the name (#68)
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[ResumeLinkLLM] = Field(default_factory=list)  # Portfolio / LinkedIn / GitHub (#68)
    summary: str = ""
    experience: list[ResumeExperienceLLM] = Field(default_factory=list)
    education: list[ResumeEducationLLM] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skill_groups: list[ResumeSkillGroupLLM] = Field(default_factory=list)  # categorised (#68)
    certifications: list[str] = Field(default_factory=list)


def _experience_to_dict(entry: ResumeExperienceLLM) -> dict[str, str]:
    """Flatten the LLM experience entry to the legacy `dict[str, str]` shape.

    Bullets collapse into a `description` string with one `- bullet` per line.
    `tools/master_resume._parse_bullets` re-splits on newlines when building the
    `ResumeMaster`, so this round-trip preserves every bullet as a separate item
    with its own stable ID.
    """
    description = "\n".join(f"- {b.strip()}" for b in entry.bullets if b.strip())
    return {
        "role": entry.role,
        "company": entry.company,
        "start_date": entry.start_date,
        "end_date": entry.end_date,
        "description": description,
    }


def _build_master_from_llm(parsed: ResumeLLMOutput) -> ResumeMaster:
    """Build a `ResumeMaster` directly from the LLM output, preserving the new
    senior-format fields (headline, links, categorised skills, per-role tech)
    that `resume_data_to_master` can't carry because they don't exist on the
    legacy `ResumeData` shape (#68).
    """
    experience = [
        ExperienceEntry(
            id=f"exp-{i + 1}",
            role=e.role,
            company=e.company,
            start_date=e.start_date,
            end_date=e.end_date,
            bullets=[
                ExperienceBullet(id=f"exp-{i + 1}-b{j + 1}", text=b.strip())
                for j, b in enumerate(e.bullets)
                if b.strip()
            ],
            tech=[t.strip() for t in e.tech if t.strip()],
        )
        for i, e in enumerate(parsed.experience)
    ]
    education = [
        EducationEntry(
            id=f"edu-{i + 1}",
            degree=ed.degree,
            school=ed.school,
            start_date=ed.start_date,
            end_date=ed.end_date,
        )
        for i, ed in enumerate(parsed.education)
    ]
    links = [
        Link(label=link.label, url=link.url) for link in parsed.links if link.url or link.label
    ]
    skill_groups = [
        SkillGroup(category=g.category, items=[s for s in g.items if s])
        for g in parsed.skill_groups
        if g.category and g.items
    ]
    return ResumeMaster(
        name=parsed.name,
        headline=parsed.headline,
        email=parsed.email,
        phone=parsed.phone,
        location=parsed.location,
        links=links,
        summary=parsed.summary,
        experience=experience,
        education=education,
        skills=list(parsed.skills),
        skill_groups=skill_groups,
        certifications=list(parsed.certifications),
    )


def parse_resume(state: ResumeOptimizerState) -> dict[str, Any]:
    """Parse resume PDF and extract structured data.

    Uses PyMuPDF to extract raw text, then LLM to structure it into
    ResumeData fields (name, experience, education, skills, etc.).
    Also reads the job description text from file or state.
    """
    logger.info("parse_resume: starting")
    errors: list[str] = list(state.errors)
    result: dict[str, Any] = {}

    if not state.resume_path:
        logger.error("parse_resume: resume_path is empty")
        errors.append("parse_resume: resume_path is empty")
        return {"errors": errors}

    # --- Extract resume text ---
    try:
        raw_text = extract_text(Path(state.resume_path))
    except Exception as exc:
        logger.error("parse_resume: PDF extraction failed: %s", exc)
        errors.append(f"parse_resume: PDF extraction failed: {exc}")
        return {"errors": errors}

    logger.debug("parse_resume: raw text (%d chars)", len(raw_text))

    # --- Structured LLM call ---
    try:
        llm = get_structured_llm(ResumeLLMOutput)
        prompt = PARSE_RESUME.format(resume_text=raw_text)
        logger.debug("parse_resume: LLM prompt: %s", prompt)
        parsed: ResumeLLMOutput = llm.invoke(prompt)
        logger.debug("parse_resume: LLM response: %s", parsed.model_dump_json())
    except ValidationError as exc:
        logger.error("parse_resume: LLM returned schema-invalid data: %s", exc)
        errors.append(f"parse_resume: LLM returned schema-invalid data: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("parse_resume: LLM call failed: %s", exc)
        errors.append(f"parse_resume: LLM call failed: {exc}")
        return {"errors": errors}

    resume_data = ResumeData(
        name=parsed.name,
        email=parsed.email,
        phone=parsed.phone,
        summary=parsed.summary,
        experience=[_experience_to_dict(e) for e in parsed.experience],
        education=[e.model_dump() for e in parsed.education],
        skills=list(parsed.skills),
        certifications=list(parsed.certifications),
        raw_text=raw_text,
    )
    result["resume"] = resume_data
    # Also build a ResumeMaster with stable IDs + the senior-format extras
    # (headline, links, skill_groups, per-role tech — #68). This path preserves
    # the new fields that the legacy ResumeData shape can't carry.
    result["master"] = _build_master_from_llm(parsed)

    # --- Read job description ---
    job_raw_text = state.job_description_text
    if not job_raw_text and state.job_description_path:
        try:
            job_raw_text = Path(state.job_description_path).read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("parse_resume: failed to read job description: %s", exc)
            errors.append(f"parse_resume: failed to read job description: {exc}")

    if job_raw_text:
        result["job_description"] = JobDescription(raw_text=job_raw_text)

    logger.info(
        "parse_resume: completed — skills=%d, experience=%d, education=%d",
        len(resume_data.skills),
        len(resume_data.experience),
        len(resume_data.education),
    )

    if errors != list(state.errors):
        result["errors"] = errors

    return result
