"""`resume-operator-server` console entry point.

Thin wrapper around uvicorn that boots the FastAPI app from `app.py`.
Kept deliberately minimal so the Tauri sidecar (Phase 2, #85) can launch
it with a fixed port flag and nothing else.
"""

from __future__ import annotations

import logging

import typer
import uvicorn

from resume_operator.config import get_settings

cli = typer.Typer(name="resume-operator-server", add_completion=False)


@cli.command()
def run(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (localhost by default)"),
    port: int = typer.Option(7421, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Hot-reload on code changes (dev only)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logging"),
) -> None:
    """Boot the FastAPI app that wraps the resume-operator graph."""
    if verbose:
        level = logging.DEBUG
    else:
        level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    uvicorn.run(
        "resume_operator.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=level,
    )


def main() -> None:
    """Typer entry point — separate fn so `pyproject.toml` can target it."""
    cli()


if __name__ == "__main__":
    main()
