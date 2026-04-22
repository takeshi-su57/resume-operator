"""Node: Generate optimized resume as PDF — deterministic render from structured data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from resume_operator.config import get_settings
from resume_operator.state import ResumeOptimizerState
from resume_operator.tools.pdf_generator import generate_pdf as create_pdf
from resume_operator.tools.style import StyleTemplate, load_style

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = "data/optimized_resume.pdf"


def generate_pdf(state: ResumeOptimizerState) -> dict[str, Any]:
    """Render `state.tailored_resume` to a PDF using the configured template + style."""
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
    style = _resolve_style(state.style_path)

    try:
        result_path = create_pdf(
            master=state.master,
            tailored=state.tailored_resume,
            output_path=Path(output_path),
            template=template,
            facts=state.facts,
            style=style,
        )
    except Exception as exc:
        logger.error("generate_pdf: PDF generation failed: %s", exc)
        errors.append(f"generate_pdf: PDF generation failed: {exc}")
        return {"errors": errors}

    file_size = result_path.stat().st_size
    logger.info(
        "generate_pdf: completed — output=%s, size=%d bytes, style=%r",
        result_path,
        file_size,
        style.name if style else "(built-in defaults)",
    )

    result: dict[str, Any] = {"output_path": str(result_path)}
    if errors != list(state.errors):
        result["errors"] = errors
    return result


def _resolve_style(explicit_path: str) -> StyleTemplate | None:
    """Pick a style template based on the precedence ladder:

      1. `state.style_path` (the `--style` flag, plumbed here by the CLI)
      2. `RESUME_STYLE_PATH` env var (via Settings.resume_style_path)
      3. `input/style.default.yaml` if it exists
      4. None → PDF generator falls back to hardcoded defaults

    Returns None when no YAML is found; `create_pdf` handles None by using
    `StyleTemplate()` directly.
    """
    if explicit_path:
        return load_style(Path(explicit_path))

    env_path = get_settings().resume_style_path
    if env_path:
        return load_style(Path(env_path))

    default_path = Path("input/style.default.yaml")
    if default_path.exists():
        return load_style(default_path)

    return None
