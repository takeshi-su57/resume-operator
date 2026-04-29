# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the lucky-resume-server sidecar.
#
# Phase 6 (#89) of the desktop GUI roadmap. Produces a single-file
# binary the Tauri shell launches as an `externalBin` sidecar — when
# the shell starts, the binary boots a localhost FastAPI server
# (default port 7421); when the shell exits, the binary is terminated.
#
# Builds with:
#     uv run python -m PyInstaller pyinstaller/lucky_resume_server.spec
#
# Output lands at `dist/lucky-resume-server.exe` on Windows; the
# `pyinstaller/build.py` wrapper renames + copies it into
# `desktop/src-tauri/binaries/` with Tauri's per-target naming
# convention.

import sys
from pathlib import Path

# We're invoked from the repo root by `python -m PyInstaller …`; the
# spec lives in `pyinstaller/`.
here = Path.cwd()

block_cipher = None


a = Analysis(
    ["../src/lucky_resume/server/main.py"],
    pathex=[str(here / "src")],
    binaries=[],
    # Data files bundled at known paths inside the PyInstaller archive:
    #
    # - `.env.example` at the root so `paths._find_env_example` can
    #   locate it via `sys._MEIPASS` and seed the per-user `.env` on
    #   first launch.
    # - `lucky_resume/data/styles/*.yaml` under the package namespace so
    #   `importlib.resources.files("lucky_resume.data.styles")` resolves
    #   inside the bundle (PyInstaller respects package layouts when the
    #   destination matches the dotted path).
    #
    # First tuple element is the source path; second is the destination
    # directory inside the bundle.
    datas=[
        (str(here / ".env.example"), "."),
        (str(here / "src" / "lucky_resume" / "data" / "styles"), "lucky_resume/data/styles"),
    ],
    # The lazy LLM provider imports in `tools/llm_provider.py` aren't
    # picked up by PyInstaller's static analysis. Force them in so
    # whichever provider the user picks at runtime is bundled.
    hiddenimports=[
        "langchain_openai",
        "langchain_anthropic",
        "langchain_google_genai",
        "uvicorn.logging",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "websockets",
        "watchfiles",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Don't ship Python's tkinter / test packages — neither are
    # needed and they bloat the binary by ~10 MB.
    excludes=[
        "tkinter",
        "test",
        "unittest",
        "pdb",
        "doctest",
        "_pytest",
        "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="lucky-resume-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-compressed binaries occasionally trigger AV false positives.
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # logging to stderr; Tauri sidecar reads both streams.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
