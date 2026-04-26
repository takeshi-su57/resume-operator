"""`GET/PUT /api/settings` — surface every env var from `config.py`.

Reads return the current `Settings` instance with API key values masked
(first 4 / last 4 characters only) so the frontend can show "key is set"
without leaking the secret back over HTTP — even on localhost this is
good hygiene. Writes persist to `.env` in the project root, invalidate
the `get_settings` cache, and take effect on the next request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import dotenv_values, set_key
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from resume_operator.config import Settings, get_settings

router = APIRouter()


# Fields whose values must be masked in GET responses.
_SECRET_FIELDS = frozenset(
    {
        "openai_api_key",
        "anthropic_api_key",
        "google_api_key",
        "openrouter_api_key",
    }
)


def _mask(value: str) -> str:
    """Preserve enough of the value that the UI can tell if it's set and
    distinguish two different keys, without exposing the whole secret."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}…{value[-4:]}"


class SettingsPayload(BaseModel):
    """The shape of GET responses — masked for secrets, full for plain fields."""

    llm_provider: str
    llm_model: str
    openai_api_key: str
    anthropic_api_key: str
    google_api_key: str
    openrouter_api_key: str
    log_level: str
    ats_skip_threshold: float
    resume_template: str
    resume_style_path: str
    enrich_threshold: int
    resume_max_iterations: int
    ats_weight_hard: float
    ats_weight_soft: float
    ats_weight_structural: float
    ats_weight_title: float
    ats_weight_measurable: float
    ats_weight_tone: float


class SettingsUpdate(BaseModel):
    """PUT payload — every field optional. Fields omitted from the request
    body are untouched on disk."""

    llm_provider: str | None = None
    llm_model: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    openrouter_api_key: str | None = None
    log_level: str | None = None
    ats_skip_threshold: float | None = None
    resume_template: str | None = None
    resume_style_path: str | None = None
    enrich_threshold: int | None = Field(default=None, ge=0)
    resume_max_iterations: int | None = Field(default=None, ge=1)
    ats_weight_hard: float | None = Field(default=None, ge=0.0, le=1.0)
    ats_weight_soft: float | None = Field(default=None, ge=0.0, le=1.0)
    ats_weight_structural: float | None = Field(default=None, ge=0.0, le=1.0)
    ats_weight_title: float | None = Field(default=None, ge=0.0, le=1.0)
    ats_weight_measurable: float | None = Field(default=None, ge=0.0, le=1.0)
    ats_weight_tone: float | None = Field(default=None, ge=0.0, le=1.0)


def _settings_to_payload(s: Settings) -> SettingsPayload:
    data: dict[str, Any] = s.model_dump()
    for field in _SECRET_FIELDS:
        data[field] = _mask(data[field])
    return SettingsPayload(**data)


def _env_path() -> Path:
    """Where `.env` lives — relative to cwd, matching pydantic-settings."""
    return Path(".env")


@router.get("/settings", response_model=SettingsPayload)
def read_settings() -> SettingsPayload:
    return _settings_to_payload(get_settings())


@router.put("/settings", response_model=SettingsPayload)
def write_settings(update: SettingsUpdate) -> SettingsPayload:
    payload = update.model_dump(exclude_none=True)
    if not payload:
        # Nothing to persist — round-trip the current values.
        return _settings_to_payload(get_settings())

    env_file = _env_path()
    env_file.touch(exist_ok=True)
    # `set_key` rewrites in-place, preserving comments and unrelated vars.
    for key, value in payload.items():
        set_key(str(env_file), key.upper(), str(value), quote_mode="never")

    # Invalidate the cached Settings so the next call sees the new values.
    get_settings.cache_clear()

    try:
        return _settings_to_payload(get_settings())
    except Exception as exc:  # pragma: no cover — defensive
        raise HTTPException(status_code=500, detail=f"reload failed: {exc}") from exc


@router.get("/settings/env", include_in_schema=False)
def debug_env_file() -> dict[str, str | None]:
    """Raw view of `.env` contents — useful for debugging, unmasked. Kept
    hidden from the OpenAPI schema so casual clients don't stumble onto
    it."""
    env_file = _env_path()
    if not env_file.exists():
        return {}
    return dotenv_values(env_file)
