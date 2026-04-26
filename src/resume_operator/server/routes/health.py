"""`GET /health` — single-purpose probe the Tauri shell uses to detect
when the sidecar is ready to accept requests. Returns in microseconds;
never hits the graph or any LLM."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from resume_operator.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_model: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
    )
