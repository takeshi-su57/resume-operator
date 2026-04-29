"""Facts bank YAML I/O.

A facts bank is an *optional* pool of items beyond the trimmed master resume:
projects, extra bullets, skills, and certifications that wouldn't fit on a
one-page master but might be relevant to a specific JD.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from lucky_resume.state import FactItem, FactsBank

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


# Header comment block re-emitted on every save — keeps facts_bank.yaml self-documenting
# even after programmatic appends (which lose free-form comments by design).
_FACTS_HEADER = """\
# facts_bank.yaml — items beyond the trimmed master resume.
#
# The optimizer (optimize_content node) gets this as a distinct pool and may
# pull items from here when they strengthen the match for a specific JD.
# `enrich` grows this file from interactive interview sessions.
#
# Conventions:
#   - Every item needs a stable `id`. `extra_bullets` may carry `role_id` to
#     splice under a specific master experience entry.
#   - `source` tags (e.g. `enrich 2026-04-21`) are metadata — safe to ignore
#     or hand-remove.
#   - A missing or empty file is valid.
"""


def save_facts(bank: FactsBank, path: Path) -> None:
    """Serialize a `FactsBank` to YAML with the canonical header comment block."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(
        bank.model_dump(exclude_defaults=False),
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    path.write_text(_FACTS_HEADER + "\n" + body, encoding="utf-8")
    logger.info(
        "save_facts: wrote %s — projects=%d, extra_bullets=%d, skills=%d, certs=%d",
        path,
        len(bank.projects),
        len(bank.extra_bullets),
        len(bank.skills_beyond_master),
        len(bank.certifications_beyond_master),
    )


def append_to_facts(
    path: Path,
    *,
    projects: list[FactItem] | None = None,
    extra_bullets: list[FactItem] | None = None,
    skills: list[str] | None = None,
    certifications: list[str] | None = None,
) -> FactsBank:
    """Load existing facts, merge in new items, write back. Returns the merged bank.

    New items are appended — existing items are never removed or reordered here.
    Callers are responsible for giving each new `FactItem` a unique `id`; this
    function does not auto-generate IDs but will de-duplicate exact-id matches
    (last write wins).
    """
    bank = load_facts(path) if path.exists() else FactsBank()

    if projects:
        bank.projects = _merge_items(bank.projects, projects)
    if extra_bullets:
        bank.extra_bullets = _merge_items(bank.extra_bullets, extra_bullets)
    if skills:
        bank.skills_beyond_master = _merge_scalars(bank.skills_beyond_master, skills)
    if certifications:
        bank.certifications_beyond_master = _merge_scalars(
            bank.certifications_beyond_master, certifications
        )

    save_facts(bank, path)
    return bank


def _merge_items(existing: list[FactItem], new: list[FactItem]) -> list[FactItem]:
    by_id: dict[str, FactItem] = {item.id: item for item in existing}
    for item in new:
        by_id[item.id] = item  # new overrides existing on id collision
    return list(by_id.values())


def _merge_scalars(existing: list[str], new: list[str]) -> list[str]:
    out = list(existing)
    for item in new:
        if item not in out:
            out.append(item)
    return out
