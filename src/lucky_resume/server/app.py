"""FastAPI app factory + top-level routes wiring.

The server binds to localhost only (the Tauri shell is the only client in
the Phase 2 roadmap; no multi-host deploy is planned). CORS is enabled
for dev so `pnpm tauri dev`'s Vite server (typically
http://localhost:1420) can hit the API during hot-reload.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lucky_resume.server.routes import (
    bootstrap,
    config,
    extract_style,
    files,
    health,
    parse_resume,
    settings,
    tasks,
)
from lucky_resume.server.tasks.lifecycle import reconcile_on_startup


def create_app() -> FastAPI:
    app = FastAPI(
        title="lucky-resume",
        version="0.1.0",
        description=(
            "Localhost server wrapping the lucky-resume graph. Consumed by "
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
    app.include_router(parse_resume.router, prefix="/api")
    app.include_router(extract_style.router, prefix="/api")
    app.include_router(bootstrap.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(config.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")

    @app.on_event("startup")
    def _reconcile_tasks() -> None:
        # Mark any task left running/awaiting_input by a previous
        # sidecar process as `interrupted`, so the UI can render an
        # honest history instead of zombie "in progress" rows.
        reconcile_on_startup()

    return app


app = create_app()
