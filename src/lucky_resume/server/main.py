"""`lucky-resume-server` console entry point.

Thin wrapper around uvicorn that boots the FastAPI app from `app.py`.
Kept deliberately minimal so the Tauri sidecar (Phase 6, #89) can launch
it with a fixed port flag and nothing else.

The app is imported by reference (not by string path) so that
PyInstaller's static analysis picks up the full module graph — under
the bundled sidecar, dynamic string-based imports through uvicorn
fail with `ModuleNotFoundError: No module named 'lucky_resume.server'`.
"""

from __future__ import annotations

import logging

import typer
import uvicorn

from lucky_resume.config import get_settings
from lucky_resume.server.app import app as fastapi_app

cli = typer.Typer(name="lucky-resume-server", add_completion=False)


@cli.command()
def run(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (localhost by default)"),
    port: int = typer.Option(7421, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Hot-reload on code changes (dev only)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logging"),
) -> None:
    """Boot the FastAPI app that wraps the lucky-resume graph."""
    if verbose:
        level = logging.DEBUG
    else:
        level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Reload mode requires the string form for uvicorn to track changes;
    # bundled (PyInstaller) sidecar uses the imported `fastapi_app`
    # object so PyInstaller's static analysis picks up the full
    # module graph — string-based imports fail at runtime in the bundle.
    if reload:
        uvicorn.run(
            "lucky_resume.server.app:app",
            host=host,
            port=port,
            reload=True,
            log_level=level,
        )
    else:
        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            log_level=level,
        )


def main() -> None:
    """Typer entry point — separate fn so `pyproject.toml` can target it."""
    cli()


if __name__ == "__main__":
    main()
