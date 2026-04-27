# [Feature]: Tauri desktop shell with sidecar + Settings + Score screens — Phase 2 of desktop GUI

GitHub issue: [#85](https://github.com/takeshi-su57/resume-operator/issues/85) · PR [#91](https://github.com/takeshi-su57/resume-operator/pull/91)

## Description

Phase 1 (#043) lands a FastAPI + WebSocket server that wraps every resume-operator command. Phase 2 — this issue — scaffolds the Tauri 2 + React + TypeScript desktop shell that consumes that server, and ships the two simplest screens (Settings + Score) to validate every piece of plumbing before Phase 3 (#045) tackles the iterative approval workspace.

## Motivation

Build the boring stuff first. HTTP round-trip, file dialogs, theming, routing, sidecar lifecycle posture — these are all easy to get subtly wrong. Validating against low-risk read-only flows surfaces issues without burning the time it takes to design + build the high-value Run screen.

## Target State

```
desktop/
├── package.json              # pnpm workspace deps
├── tsconfig.json             # strict TS, @ alias → ./src
├── vite.config.ts            # locked port 1420 (Tauri convention), TAURI_ENV_* prefixes
├── tailwind.config.ts        # Linear-style dark theme — single accent (cyan), JetBrains Mono body
├── postcss.config.js
├── index.html
├── src/
│   ├── main.tsx              # TanStack Query + React Router providers
│   ├── App.tsx               # Routes shell — Score and Settings enabled, others stub
│   ├── globals.css           # base layer + .panel / .row / .kbd / .focus-ring
│   ├── lib/{api,cn}.ts       # `fetch` wrapper + TanStack hooks for /health, /api/settings, /api/score
│   ├── components/
│   │   ├── ui/{button,input,label,select}.tsx  # Radix + cva
│   │   ├── nav-rail.tsx      # left sidebar with phase-numbered stubs
│   │   ├── top-bar.tsx       # engine-status pill (polls /health)
│   │   ├── file-picker.tsx   # @tauri-apps/plugin-dialog wrapper with browser fallback
│   │   └── ats-report.tsx    # composite + structural + skills tables + tone flags
│   └── screens/{score,settings}.tsx
└── src-tauri/                # Rust shell
    ├── Cargo.toml            # Tauri 2 + plugin-dialog + plugin-shell + plugin-log
    ├── tauri.conf.json       # 1280×800 window, MSI bundle target, Windows-first
    ├── capabilities/default.json
    ├── icons/                # placeholder cyan squares (real icons in Phase 6)
    └── src/{main,lib}.rs     # Builder + plugins; opens devtools in debug
```

`cd desktop && pnpm tauri dev` opens a window. Two screens exist:

**Settings** — every env var from `src/resume_operator/config.py` exposed as a form: LLM provider + model, four API keys (masked on read), log level, ATS skip threshold, enrich threshold, max approval iterations, resume style path, the six #042 ATS composite weights. Reads via `useSettings`, writes via `useUpdateSettings` — GET masks API keys (`sk-p…7890`); typing into a key field is a brand-new value. Save/Reset pair, dirty-flag tracking.

**Score** — two file pickers (master YAML preferred, legacy resume PDF fallback) + job description text → `POST /api/score` → multi-dim ATSReport on the right. Mirrors what the CLI's `score` prints in Rich tables (composite + reasoning, structural checks with status glyphs, hard + soft skill tables with resume-vs-JD counts, tone flags, keyword gaps).

### Visual direction

Pro/dense Linear-style — agreed in the planning phase. Restraint over decoration:

- one accent color (`#22D3EE` cyan-400)
- one font for body (JetBrains Mono); Inter for the few headings
- flat panels with hairline borders (`#27272A` on `#161618`)
- `data-no-select` on chrome (rail, top bar) so the user only selects content
- compact rows — text-sm everywhere except composite score, no big padding

### Sidecar lifecycle deferred

Phase 2 keeps the dev workflow as two terminals (`uv run resume-operator-server` in one, `pnpm tauri:dev` in the other). Phase 6 (#048) wires Tauri's externalBin once PyInstaller produces a bundled binary.

### Plain-browser dev fallback

If MSVC's `link.exe` isn't installed (Visual Studio's "Desktop development with C++" workload is required), `pnpm dev` (plain Vite) serves the screens at http://localhost:1420 in a regular browser. The OS file dialog is a no-op outside Tauri — type paths in directly while debugging layout. Documented in `desktop/README.md`.

## Success Metrics

- `cd desktop && pnpm tauri dev` opens a window with no console errors.
- Filling in an OpenAI key in Settings → closing the app → reopening shows the key persisted.
- Running a Score against `data/master_resume.yaml` + `input/job.txt` produces a visual ATS report that matches the CLI's `score` output dimension-for-dimension.
- Keyboard-only navigation works for both screens.

## Key Files

- `desktop/package.json` — Vite, React, TanStack Query, Radix, Tailwind, Tauri CLI, Lucide, zustand, react-router.
- `desktop/tsconfig.json`, `desktop/vite.config.ts`, `desktop/tailwind.config.ts`, `desktop/postcss.config.js`.
- `desktop/index.html`, `desktop/src/main.tsx`.
- `desktop/src/lib/{api,cn}.ts`.
- `desktop/src/components/{nav-rail,top-bar,file-picker,ats-report}.tsx`.
- `desktop/src/components/ui/{button,input,label,select}.tsx`.
- `desktop/src/screens/{score,settings}.tsx`.
- `desktop/src-tauri/{Cargo.toml,build.rs,tauri.conf.json}`.
- `desktop/src-tauri/src/{main,lib}.rs`.
- `desktop/src-tauri/capabilities/default.json`.
- `desktop/src-tauri/icons/*` (placeholders).
- `desktop/.gitignore`, `desktop/README.md`, root `.gitignore` (negate `lib/` for `desktop/src/lib/`).

## Dependencies

- **#043** (Phase 1 server) — must be reachable on `127.0.0.1:7421` for the screens to load data.

## Out of Scope

- Run / Bootstrap / Parse / Extract Style screens (Phases 3-5).
- Sidecar lifecycle (Phase 6).
- Cross-platform builds — Windows-first; macOS/Linux later.

## Labels

`enhancement`, `priority:high`
