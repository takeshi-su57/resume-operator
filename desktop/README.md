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

```bash
# Terminal 1 — boot the Python server (listens on 127.0.0.1:7421)
cd ..
uv run resume-operator-server

# Terminal 2 — boot the Tauri shell
cd desktop
pnpm install
pnpm tauri:dev
```

The Tauri window opens against Vite's localhost:1420; HTTP and
WebSocket calls hit the sidecar at 127.0.0.1:7421 (overridable via
`VITE_SERVER_PORT`).

## Dev mode (plain browser, no Tauri)

If the Rust shell doesn't compile yet (no MSVC) you can still iterate
on the React side in a regular browser:

```bash
# Terminal 1 — Python server (same as above)
uv run resume-operator-server

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

```bash
pnpm tauri:build
```

Produces a Windows MSI under `src-tauri/target/release/bundle/msi/`.
Phase 6 (#89) wires up the PyInstaller-bundled Python sidecar; until
then `tauri build` produces a shell that needs the dev sidecar running.
