"""Node: Extract structured data from resume PDF."""

import logging
from pathlib import Path
from typing import Any

from resume_operator.prompts.resume_parsing import PARSE_RESUME
from resume_operator.state import JobDescription, ResumeData, ResumeOptimizerState
from resume_operator.tools.json_parser import extract_json
from resume_operator.tools.llm_provider import get_llm
from resume_operator.tools.pdf_parser import extract_text

logger = logging.getLogger(__name__)


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

    # --- Call LLM to structure the resume ---
    try:
        llm = get_llm()
        prompt = PARSE_RESUME.format(resume_text=raw_text)
        logger.debug("parse_resume: LLM prompt: %s", prompt)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        logger.debug("parse_resume: LLM response: %s", content)
        parsed = extract_json(str(content))
    except ValueError as exc:
        logger.error("parse_resume: LLM returned invalid JSON: %s", exc)
        errors.append(f"parse_resume: LLM returned invalid JSON: {exc}")
        return {"errors": errors}
    except Exception as exc:
        logger.error("parse_resume: LLM call failed: %s", exc)
        errors.append(f"parse_resume: LLM call failed: {exc}")
        return {"errors": errors}

    # --- Build ResumeData ---
    resume_data = ResumeData(
        name=parsed.get("name") or "",
        email=parsed.get("email") or "",
        phone=parsed.get("phone") or "",
        summary=parsed.get("summary") or "",
        experience=parsed.get("experience") or [],
        education=parsed.get("education") or [],
        skills=parsed.get("skills") or [],
        certifications=parsed.get("certifications") or [],
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
