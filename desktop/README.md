# resume-operator desktop

Tauri 2 + React + TypeScript shell for the [resume-operator](../) Python engine.

Phase 2 of a six-phase desktop GUI roadmap (issues #84–#89). This phase
ships:

- **Settings** — every env var from `config.py` exposed as a form. API
  keys arrive masked; writes persist to `.env` in the project root.
- **Score** — pick a master YAML + job description, see the multi-dim
  ATSReport (#81) rendered as a compact dashboard.

The Run / Bootstrap / Parse / Extract-style screens land in Phases 3-5.

## Prerequisites (one-time)

- **Node 20+** and **pnpm 9+** for the JS toolchain.
- **Rust stable 1.85+** (`rustup update stable`). Earlier versions can't
  compile current Tauri 2 deps — they need edition 2024.
- **Visual Studio Build Tools** with the **"Desktop development with
  C++"** workload, for MSVC's `link.exe`. Without it `cargo check`
  fails with `link: extra operand …rcgu.o` because `C:\Program
  Files\Git\usr\bin\link.exe` (GNU coreutils) shadows MSVC's linker.
  Install via Visual Studio Installer → Modify → Workloads → check
  "Desktop development with C++" → Modify.

## Dev mode (Tauri shell)

Dev binds the engine to **127.0.0.1:7422** so it can coexist with an
installed production build (which holds 7421). The frontend's
`.env.development` sets `VITE_SERVER_PORT=7422` to match.

```bash
# Terminal 1 — boot the Python server on the dev port
cd ..
uv run lucky-resume-server --port 7422

# Terminal 2 — boot the Tauri shell
cd desktop
pnpm install
pnpm tauri:dev
```

The Tauri window opens against Vite's localhost:1420; HTTP and
WebSocket calls hit the sidecar at 127.0.0.1:7422. Override via
`VITE_SERVER_PORT` if you need a different port.

## Dev mode (plain browser, no Tauri)

If the Rust shell doesn't compile yet (no MSVC) you can still iterate
on the React side in a regular browser:

```bash
# Terminal 1 — Python server (same as above)
uv run lucky-resume-server --port 7422

# Terminal 2 — Vite only, no Tauri
cd desktop
pnpm install
pnpm dev   # serves http://localhost:1420 in a regular browser
```

The OS file dialog (`@tauri-apps/plugin-dialog`) is a no-op in this
mode — picker buttons open nothing, so type paths in directly while
debugging the layout.

## Stack

| Concern | Choice |
|---------|--------|
| Build | Vite 6 |
| Language | TypeScript (strict) |
| UI | React 18 + Radix UI primitives |
| Styling | Tailwind CSS v3 — Linear-style dark theme |
| State | Zustand (per-screen ephemeral) |
| HTTP | TanStack Query |
| Routing | React Router v7 |
| Icons | Lucide |
| Shell | Tauri 2 |

## Build

The release pipeline bundles the Python server with PyInstaller and
ships it as a Tauri sidecar inside the MSI installer.

```powershell
# From the repo root, on Windows with MSVC C++ tools installed:
desktop/scripts/release.ps1
```

The script does, in order:

1. **`uv sync`** — installs PyInstaller alongside the runtime deps.
2. **`uv run python pyinstaller/build.py`** — runs PyInstaller from
   `pyinstaller/resume_operator_server.spec`, smoke-tests the produced
   binary by booting it on port 7421 and hitting `/health`, then
   copies it into
   `desktop/src-tauri/binaries/resume-operator-server-x86_64-pc-windows-msvc.exe`
   with Tauri's per-target naming convention.
3. **`pnpm install` + `pnpm tauri:build`** — Tauri picks up the
   sidecar via `tauri.conf.json`'s `bundle.externalBin`, embeds it in
   the MSI, and produces
   `desktop/src-tauri/target/release/bundle/msi/resume-operator_0.1.0_x64_en-US.msi`.

The Tauri shell launches the sidecar on startup
([`src-tauri/src/lib.rs::spawn_sidecar`](src-tauri/src/lib.rs)) and
terminates it when the window closes — the installed app is
self-contained, with no `uv` or Python on PATH required.

The MSI is **unsigned** by design — it's a personal-use installer.
Windows SmartScreen will prompt on first run; click "More info →
Run anyway." For shareable signed builds, set
`bundle.windows.certificateThumbprint` to a real cert thumbprint and
re-run `tauri build`.
