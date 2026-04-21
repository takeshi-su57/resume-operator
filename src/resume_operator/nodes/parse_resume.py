"""Node: Extract structured data from resume PDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.resume_parsing import PARSE_RESUME
from resume_operator.state import JobDescription, ResumeData, ResumeOptimizerState
from resume_operator.tools.llm_provider import get_structured_llm
from resume_operator.tools.pdf_parser import extract_text

logger = logging.getLogger(__name__)


class ResumeExperienceLLM(BaseModel):
    role: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class ResumeEducationLLM(BaseModel):
    degree: str = ""
    school: str = ""
    start_date: str = ""
    end_date: str = ""


class ResumeLLMOutput(BaseModel):
    """Schema handed to `with_structured_output` — the LLM fills this in directly.

    Fixed sub-schemas (not raw dicts) so the generated JSON schema is compatible
    with OpenAI's strict mode.
    """

    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    experience: list[ResumeExperienceLLM] = Field(default_factory=list)
    education: list[ResumeEducationLLM] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


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
        experience=[e.model_dump() for e in parsed.experience],
        education=[e.model_dump() for e in parsed.education],
        skills=list(parsed.skills),
        certifications=list(parsed.certifications),
        raw_text=raw_text,
    )
    result["resume"] = resume_data

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
