"""Node: Generate optimized resume as PDF — deterministic render from structured data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from resume_operator.config import get_settings
from resume_operator.state import ResumeOptimizerState
from resume_operator.tools.pdf_generator import generate_pdf as create_pdf

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = "data/optimized_resume.pdf"


def generate_pdf(state: ResumeOptimizerState) -> dict[str, Any]:
    """Render `state.tailored_resume` to a PDF using the configured template."""
    logger.info("generate_pdf: starting")
    errors: list[str] = list(state.errors)

    if not state.tailored_resume.items:
        logger.warning(
            "generate_pdf: skipping — no tailored items (optimize_content may have failed)"
        )
        errors.append("generate_pdf: skipping — no tailored items")
        return {"errors": errors}

    output_path = state.output_path or DEFAULT_OUTPUT_PATH
    template = get_settings().resume_template

    try:
        result_path = create_pdf(
            master=state.master,
            tailored=state.tailored_resume,
            output_path=Path(output_path),
            template=template,
            facts=state.facts,
        )
    except Exception as exc:
        logger.error("generate_pdf: PDF generation failed: %s", exc)
        errors.append(f"generate_pdf: PDF generation failed: {exc}")
        return {"errors": errors}

    file_size = result_path.stat().st_size
    logger.info("generate_pdf: completed — output=%s, size=%d bytes", result_path, file_size)

    result: dict[str, Any] = {"output_path": str(result_path)}
    if errors != list(state.errors):
        result["errors"] = errors
    return result
