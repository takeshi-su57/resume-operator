"""Facts bank YAML I/O.

A facts bank is an *optional* pool of items beyond the trimmed master resume:
projects, extra bullets, skills, and certifications that wouldn't fit on a
one-page master but might be relevant to a specific JD.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from resume_operator.state import FactsBank

logger = logging.getLogger(__name__)


class FactsBankError(ValueError):
    """Raised when the facts bank YAML exists but is malformed."""


def load_facts(path: Path | None) -> FactsBank:
    """Load a facts bank YAML. Returns an empty bank if `path` is None or missing.

    Raises `FactsBankError` only on present-but-malformed files — a missing
    facts bank is not an error (the master resume is sufficient on its own).
    """
    if path is None or not path.exists():
        logger.debug("load_facts: no facts bank at %s — using empty bank", path)
        return FactsBank()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FactsBankError(f"facts bank YAML parse error: {exc}") from exc
    if raw is None:
        logger.debug("load_facts: %s is empty — using empty bank", path)
        return FactsBank()
    if not isinstance(raw, dict):
        raise FactsBankError(
            f"facts bank must be a mapping at the top level, got {type(raw).__name__}"
        )
    try:
        bank = FactsBank.model_validate(raw)
    except Exception as exc:
        raise FactsBankError(f"facts bank schema validation failed: {exc}") from exc
    logger.info(
        "load_facts: loaded %s — projects=%d, extra_bullets=%d, skills=%d, certs=%d",
        path,
        len(bank.projects),
        len(bank.extra_bullets),
        len(bank.skills_beyond_master),
        len(bank.certifications_beyond_master),
    )
    return bank
