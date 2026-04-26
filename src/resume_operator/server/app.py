"""FastAPI app factory + top-level routes wiring.

The server binds to localhost only (the Tauri shell is the only client in
the Phase 2 roadmap; no multi-host deploy is planned). CORS is enabled
for dev so `pnpm tauri dev`'s Vite server (typically
http://localhost:1420) can hit the API during hot-reload.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from resume_operator.server.routes import (
    bootstrap,
    extract_style,
    health,
    parse_resume,
    run,
    score,
    settings,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="resume-operator",
        version="0.1.0",
        description=(
            "Localhost server wrapping the resume-operator graph. Consumed by "
            "the Tauri desktop shell; the CLI is a peer surface."
        ),
    )
    # The Tauri shell ships its own frontend bundle at a `tauri://` origin, so
    # strict CORS isn't needed in production. Dev mode hits `localhost:1420`
    # from Vite — allow all localhost/loopback origins to keep the pipeline
    # friction-free. The server doesn't bind to non-loopback anyway.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(settings.router, prefix="/api")
    app.include_router(score.router, prefix="/api")
    app.include_router(parse_resume.router, prefix="/api")
    app.include_router(extract_style.router, prefix="/api")
    app.include_router(bootstrap.router, prefix="/api")
    app.include_router(run.router, prefix="/api")
    return app


app = create_app()
