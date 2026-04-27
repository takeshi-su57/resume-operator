# [Feature]: PyInstaller sidecar + Tauri MSI installer for Windows — Phase 6 of desktop GUI

GitHub issue: [#89](https://github.com/takeshi-su57/resume-operator/issues/89) · PR [#95](https://github.com/takeshi-su57/resume-operator/pull/95)

## Description

Phases 1-5 (#043-#047) deliver a working GUI via `cd desktop && pnpm tauri dev` — with Python invoked from the local `uv` environment. Phase 6 — this issue — produces a real Windows installer so the app can live on the machine without a dev stack. Aligned with the planning decision to target **one-machine installer** (personal Windows use, no cross-platform distribution yet, no code signing).

## Motivation

The dev workflow requires `uv`, Python 3.12, MSVC C++ tools, Rust, Node, pnpm. That's fine for the developer; not fine for the daily-driver use case. PyInstaller bundles the Python server into a single binary that Tauri ships inside the MSI; the installed app is self-contained.

## Target State

### Python side: PyInstaller bundle

- `pyinstaller/resume_operator_server.spec` — entry point + hidden imports for the lazy LLM-provider modules in `tools/llm_provider.py` and uvicorn's runtime-loaded protocol / loop / lifespan submodules. Excludes tkinter / pytest / unittest to keep the binary closer to 60 MB.
- `pyinstaller/build.py` — one-shot build wrapper: PyInstaller → smoke-test (boot the binary, hit `/health`, kill) → copy into `desktop/src-tauri/binaries/` with Tauri's per-target naming convention (e.g. `resume-operator-server-x86_64-pc-windows-msvc.exe`). `--skip-smoke` short-circuits the smoke test for CI.
- `server/main.py` — imports the FastAPI `app` object directly (instead of via the `"resume_operator.server.app:app"` string form uvicorn defaults to) so PyInstaller's static analysis picks up the full module graph. Without this, the bundled sidecar crashes at launch with `ModuleNotFoundError: No module named 'resume_operator.server'`. Reload mode keeps using the string form because uvicorn's hot reloader needs the qualified module path; reload is dev-only and never enabled in the bundle.

### Rust side: sidecar lifecycle + MSI bundle

- `src-tauri/src/lib.rs` — `spawn_sidecar` + `terminate_sidecar` keyed on a `SidecarState(Mutex<Option<CommandChild>>)` managed state. Tauri's `shell.sidecar(...)` resolves the binary by joining the app resource dir with the configured name; the sidecar listens on `127.0.0.1:7421`, matching the frontend's `api.ts`. In dev mode (`pnpm tauri:dev`) the sidecar binary may be missing — the helper logs a warning and tolerates it, so the developer's `uv run resume-operator-server` in a separate terminal keeps working.
- `src-tauri/tauri.conf.json` — `bundle.externalBin: ["binaries/resume-operator-server"]`. Tauri matches per-target suffixes at bundle time so the MSI pulls in the right per-platform binary.
- `src-tauri/capabilities/default.json` — grants the shell `shell:allow-execute` permission scoped to the sidecar binary + the exact `--port 7421 --host 127.0.0.1` argument list.
- `desktop/scripts/release.ps1` — one-shot Windows release pipeline: `uv sync` → `python pyinstaller/build.py` → `pnpm install` → `pnpm tauri:build` → reports the produced MSI path.

### App identity + signing posture

- App identifier: `security.klyro.resume-operator` (personal-use namespace, not distributed).
- `bundle.windows.certificateThumbprint = null` — explicitly unsigned. Windows SmartScreen will prompt on first run; click "More info → Run anyway." For shareable signed builds, set the thumbprint to a real cert and re-run `tauri build`.

### .gitignore

`desktop/src-tauri/binaries/` is ignored — the 60 MB sidecar binary is regenerated per-platform at release time. The `pyinstaller/*.spec` files are explicitly *not* ignored (root `.gitignore`'s blanket `*.spec` is negated for that path), since the spec is hand-authored source.

## Success Metrics

- `python pyinstaller/build.py` completes cleanly, smoke-tests the binary against the live LLM provider, and installs into `desktop/src-tauri/binaries/`.
- `pnpm tauri:build` completes cleanly, produces an `.msi` under `desktop/src-tauri/target/release/bundle/msi/`.
- Installing the `.msi` on the dev machine registers the app in Start menu + Add/Remove Programs.
- Launching the installed app **on a VM or clean user without `uv` or Python 3.12 on PATH** successfully runs an end-to-end tailor cycle.
- Uninstall via Add/Remove Programs cleanly removes the app + sidecar binary.
- First-launch experience: window opens within 3 seconds; engine splash lasts ≤ 2 s.

## Key Files

- `pyinstaller/resume_operator_server.spec` (NEW).
- `pyinstaller/build.py` (NEW).
- `src/resume_operator/server/main.py` — import `fastapi_app` by reference for non-reload mode.
- `desktop/src-tauri/src/lib.rs` — `spawn_sidecar`, `terminate_sidecar`.
- `desktop/src-tauri/tauri.conf.json` — `bundle.externalBin`.
- `desktop/src-tauri/capabilities/default.json` — `shell:allow-execute` scoped to the sidecar.
- `desktop/scripts/release.ps1` (NEW).
- `desktop/.gitignore` — ignore `src-tauri/binaries/`.
- `.gitignore` (root) — negate `*.spec` rule for `pyinstaller/*.spec`.
- `desktop/README.md` — release flow + unsigned-MSI callout.
- `pyproject.toml` — `pyinstaller` dev dep.

## Dependencies

- **#047** (Phase 5) — every screen the MSI ships needs to exist first.

## Out of Scope

- macOS / Linux builds — Tauri supports both, but each platform needs its own sidecar build (`aarch64-apple-darwin`, `x86_64-unknown-linux-gnu`, etc.). Same pipeline; out of scope for v1.
- Code signing — would require ~$100/year cert + a proper CI pipeline. Personal-use only for now.
- Auto-update — not needed for personal use.
- Telemetry — not needed for personal use.

## Labels

`enhancement`, `priority:high`
