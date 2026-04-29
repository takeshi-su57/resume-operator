"""Node: Generate optimized resume as PDF — deterministic render from structured data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lucky_resume.config import get_settings
from lucky_resume.events import node_span
from lucky_resume.state import ResumeOptimizerState
from lucky_resume.tools.builtin_styles import load_builtin_style, resolve_style_source
from lucky_resume.tools.pdf_generator import generate_pdf as create_pdf
from lucky_resume.tools.style import StyleTemplate, load_style

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = "data/optimized_resume.pdf"


def generate_pdf(state: ResumeOptimizerState) -> dict[str, Any]:
    """Render `state.tailored_resume` to a PDF using the configured template + style."""
    with node_span("generate_pdf"):
        return _generate_pdf_body(state)


def _generate_pdf_body(state: ResumeOptimizerState) -> dict[str, Any]:
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
      3. `input/style.default.yaml` if it exists (local-checkout fallback)
      4. `builtin:default` from the package bundle — always available
         on a fresh install since the YAML ships inside the wheel /
         PyInstaller bundle.

    Steps 1-2 also honor the ``builtin:<name>`` pseudo-path; passing
    ``builtin:consolas`` as `--style` or `RESUME_STYLE_PATH` resolves to
    the bundled YAML via `tools.builtin_styles.resolve_style_source`.
    """
    if explicit_path:
        return load_style(resolve_style_source(explicit_path))

    env_path = get_settings().resume_style_path
    if env_path:
        return load_style(resolve_style_source(env_path))

    legacy = Path("input/style.default.yaml")
    if legacy.exists():
        return load_style(legacy)

    # Final fallback: the bundled default. Always present in a working
    # install, so the renderer never has to fall back to its own
    # hardcoded constants for a brand-new user.
    return load_builtin_style("default")
