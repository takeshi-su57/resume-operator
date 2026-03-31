"""Node: Generate optimized resume as PDF."""

import logging
from pathlib import Path
from typing import Any

from resume_operator.state import ResumeOptimizerState
from resume_operator.tools.pdf_generator import generate_pdf as create_pdf

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = "data/optimized_resume.pdf"


def generate_pdf(state: ResumeOptimizerState) -> dict[str, Any]:
    """Generate PDF from optimized resume content using ReportLab.

    Takes the optimized resume sections and renders them into a
    professionally formatted PDF file.
    """
    logger.info("generate_pdf: starting")
    errors: list[str] = list(state.errors)

    output_path = state.output_path or DEFAULT_OUTPUT_PATH

    try:
        result_path = create_pdf(state.optimized_resume.sections, Path(output_path))
    except Exception as exc:
        logger.error("generate_pdf: PDF generation failed: %s", exc)
        errors.append(f"generate_pdf: PDF generation failed: {exc}")
        return {"errors": errors}

    file_size = result_path.stat().st_size
    logger.info(
        "generate_pdf: completed — output=%s, size=%d bytes",
        result_path,
        file_size,
    )

    result: dict[str, Any] = {"output_path": str(result_path)}
    if errors != list(state.errors):
        result["errors"] = errors
    return result
