"""Node: Extract structured data from resume PDF."""

import json
import logging
from pathlib import Path
from typing import Any

from resume_operator.prompts.resume_parsing import PARSE_RESUME
from resume_operator.state import JobDescription, ResumeData, ResumeOptimizerState
from resume_operator.tools.llm_provider import get_llm
from resume_operator.tools.pdf_parser import extract_text

logger = logging.getLogger(__name__)


def parse_resume(state: ResumeOptimizerState) -> dict[str, Any]:
    """Parse resume PDF and extract structured data.

    Uses PyMuPDF to extract raw text, then LLM to structure it into
    ResumeData fields (name, experience, education, skills, etc.).
    Also reads the job description text from file or state.
    """
    errors: list[str] = list(state.errors)
    result: dict[str, Any] = {}

    # --- Extract resume text ---
    try:
        raw_text = extract_text(Path(state.resume_path))
    except Exception as exc:
        errors.append(f"parse_resume: PDF extraction failed: {exc}")
        return {"errors": errors}

    # --- Call LLM to structure the resume ---
    try:
        llm = get_llm()
        prompt = PARSE_RESUME.format(resume_text=raw_text)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(str(content))
    except json.JSONDecodeError as exc:
        errors.append(f"parse_resume: LLM returned invalid JSON: {exc}")
        return {"errors": errors}
    except Exception as exc:
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
            errors.append(f"parse_resume: failed to read job description: {exc}")

    if job_raw_text:
        result["job_description"] = JobDescription(raw_text=job_raw_text)

    if errors != list(state.errors):
        result["errors"] = errors

    return result
