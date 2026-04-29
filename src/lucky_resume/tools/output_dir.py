"""Compute and reserve a per-application output folder.

Folder naming: `{parent}/{YYYY-MM-DD}_{slug}/`. Slug priority:
  1. Explicit `company` name (if known)
  2. Job-description filename stem
  3. Short hash of the JD text (as a last resort)

Collisions append `-2`, `-3`, etc. so concurrent or repeat runs against the
same JD never overwrite each other.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PARENT = Path("data/applications")
_SLUG_FALLBACK = "untitled"


def resolve_output_dir(
    parent: Path | None,
    jd_path: Path | None,
    jd_text: str,
    company: str | None = None,
    today: date | None = None,
) -> Path:
    """Compute an unused output folder under `parent` for this run.

    The folder is created on disk so concurrent runs that race for the same
    name don't both succeed.
    """
    base = parent or DEFAULT_PARENT
    base.mkdir(parents=True, exist_ok=True)

    slug = _pick_slug(company, jd_path, jd_text)
    day = (today or date.today()).strftime("%Y-%m-%d")
    candidate = base / f"{day}_{slug}"
    counter = 2
    while candidate.exists():
        candidate = base / f"{day}_{slug}-{counter}"
        counter += 1

    candidate.mkdir(parents=True, exist_ok=False)
    logger.info("output_dir: reserved %s", candidate)
    return candidate


def _pick_slug(company: str | None, jd_path: Path | None, jd_text: str) -> str:
    if company:
        slug = _slugify(company)
        if slug:
            return slug
    if jd_path is not None:
        slug = _slugify(jd_path.stem)
        if slug:
            return slug
    if jd_text:
        digest = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()[:8]
        return f"jd-{digest}"
    return _SLUG_FALLBACK


def _slugify(value: str) -> str:
    """Lower, ASCII-only, hyphen-separated. Returns empty string for unusable input."""
    cleaned = value.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    cleaned = cleaned.strip("-")
    return cleaned[:60]  # cap to keep paths reasonable
