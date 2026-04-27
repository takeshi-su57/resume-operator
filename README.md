# resume-operator

[![CI](https://github.com/takeshi-su57/resume-operator/actions/workflows/ci.yml/badge.svg)](https://github.com/takeshi-su57/resume-operator/actions/workflows/ci.yml)

Automatically tailors resumes to match job descriptions by highlighting relevant skills and experience while keeping the original profile intact. Ships as both a **CLI** and a **Tauri desktop app**.

## Features

- **`master_resume.yaml`** as hand-maintained source of truth (no LLM for ingestion)
- One-time `bootstrap` command to seed the YAML from an existing PDF
- Multi-dimensional ATS (#042) compatibility scoring — composite + per-dimension breakdown
- Gap analysis — identifies missing keywords and weak areas
- LLM-powered content optimization tailored to the job
- Iterative approval loop (#040) — accept / reject / fix proposals one by one
- Auto-enrichment interview when the tailor comes back thin
- Optimized resume PDF generation (ReportLab)
- Configurable LLM provider (OpenAI, Anthropic, Google, OpenRouter)
- **Two surfaces, one engine**:
  - CLI (Typer + Rich) for terminal-driven workflows
  - Desktop app (Tauri 2 + React + TypeScript) with a pro/dense Linear-style UI for the iterative approval workspace
- Local FastAPI + WebSocket server (`resume-operator-server`) — the engine the desktop shell consumes; also a programmable surface for any localhost client

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language (engine) | Python 3.12+ |
| Agent framework | LangGraph (StateGraph) |
| LLM | LangChain (OpenAI / Anthropic / Google / OpenRouter) |
| PDF parsing | PyMuPDF |
| PDF generation | ReportLab |
| CLI | Typer + Rich |
| Server | FastAPI + uvicorn + websockets |
| Config | Pydantic Settings + python-dotenv |
| Linting | Ruff |
| Type checking | mypy (strict) |
| Testing | pytest |
| Desktop shell | Tauri 2 (Rust) |
| Desktop frontend | React 18 + TypeScript + Vite + Tailwind v3 + Radix UI |
| Desktop state | TanStack Query (HTTP) + zustand (session) |
| Installer | PyInstaller (Python sidecar) + Tauri MSI |

## Project Structure

```
src/resume_operator/
├── main.py              # CLI entry point (Typer)
├── config.py            # Pydantic Settings (env vars)
├── state.py             # ResumeOptimizerState (central data contract)
├── graph.py             # LangGraph StateGraph
├── events.py            # NodeEventEmitter — node lifecycle events
├── prompter.py          # Prompter protocol — abstracts user interaction
├── prompters/           # CLI implementation (RichPrompter)
├── flows/               # approval + auto-enrich orchestration (Prompter-driven)
├── nodes/               # one node function per file
├── tools/               # I/O utilities (PDF, LLM, YAML, approval flow)
├── prompts/             # LLM prompt templates
└── server/              # FastAPI + WebSocket layer for the desktop GUI
    ├── app.py           # FastAPI app factory
    ├── main.py          # `resume-operator-server` console entry
    ├── ws_prompter.py   # WebSocketPrompter — drives flows over WS
    ├── session_runner.py
    └── routes/          # /api/{settings,score,parse-resume,extract-style,run,bootstrap,health}

desktop/                 # Tauri 2 + React desktop app
├── package.json         # pnpm-managed JS deps
├── src/                 # React + TS frontend
│   ├── lib/             # api.ts (HTTP) + ws.ts (WebSocket) + events.ts (protocol)
│   ├── components/      # UI primitives (Button/Input/Select), nav rail, top bar, ats-report
│   ├── screens/
│   │   ├── home.tsx
│   │   ├── run/         # three-pane Run workspace + approval / enrichment cards
│   │   ├── score.tsx
│   │   ├── bootstrap.tsx
│   │   ├── parse-resume.tsx
│   │   ├── extract-style.tsx
│   │   └── settings.tsx
│   └── state/run-session.ts  # zustand store
└── src-tauri/           # Rust shell — sidecar lifecycle, MSI bundle config

pyinstaller/
├── resume_operator_server.spec   # PyInstaller spec
└── build.py             # one-shot bundle + smoke-test + install into Tauri sidecar dir

input/
├── master_resume.example.yaml   # schema example — copy and edit
└── job.txt
tests/                   # 344 pytest tests (CLI + flows + server)
data/                    # runtime output — git-ignored
docs/                    # guides + architecture + ADRs + issue specs
```

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- An LLM API key (OpenAI, Anthropic, Google, or OpenRouter)

For the desktop app:

- Node 20+ and pnpm 9+
- Rust stable 1.85+ (`rustup update stable`)
- Visual Studio Build Tools with the **"Desktop development with C++"** workload (Windows only — Tauri 2's Rust deps need MSVC `link.exe`)

## Quick Start — CLI

```bash
git clone <repo-url>
cd resume-operator
uv sync --dev

cp .env.example .env
# Edit .env — add your LLM API key

# One-time: bootstrap master_resume.yaml from an existing PDF
uv run python -m resume_operator bootstrap --resume my-resume.pdf --output data/master_resume.yaml
# Review and hand-edit data/master_resume.yaml

# Run the optimizer (writes into data/applications/{date}_{slug}/)
uv run python -m resume_operator run \
  --master data/master_resume.yaml \
  --facts data/facts_bank.yaml \
  --job job_description.txt
# Output: resume.pdf, results.json, tailored.yaml, diff.md
```

## Quick Start — Desktop app (dev mode)

```bash
# Terminal 1 — boot the engine on 127.0.0.1:7421
uv run resume-operator-server

# Terminal 2 — boot the Tauri shell
cd desktop
pnpm install
pnpm tauri:dev
```

The window opens against Vite's `localhost:1420`; HTTP and WebSocket calls hit the engine on `127.0.0.1:7421`. Settings persist to `.env` in the project root.

For a full walkthrough of either surface, see [How to Use](docs/guides/usage.md).

## Building a Windows installer

```powershell
desktop/scripts/release.ps1
```

The script bundles the Python server with PyInstaller, copies it into the Tauri sidecar directory, and produces an unsigned `.msi` under `desktop/src-tauri/target/release/bundle/msi/`. See [How to Deploy](docs/guides/deployment.md#desktop-installer-windows).

## Commands

### CLI (`resume-operator`)

| Command | Description |
|---------|-------------|
| `uv run python -m resume_operator run --master <yaml> --job <job> [--style <yaml>] [--max-iter N] [--no-approve] [--no-enrich]` | Full pipeline. Default: enters the iterative approval loop and offers auto-enrichment when the tailor is thin. |
| `uv run python -m resume_operator bootstrap --resume <pdf>` | One-time: PDF → `master_resume.yaml` with a senior-format interview. |
| `uv run python -m resume_operator extract-style --from <docx> --output <yaml>` | Derive a StyleTemplate from a reference `.docx` CV. |
| `uv run python -m resume_operator parse-resume --resume <pdf>` | Inspect what the LLM extracts from a PDF (no YAML write). |
| `uv run python -m resume_operator score --master <yaml> --job <job>` | Multi-dimensional ATS report only — read-only. |

### Server (`resume-operator-server`)

| Command | Description |
|---------|-------------|
| `uv run resume-operator-server [--port 7421] [--host 127.0.0.1] [--reload]` | Boot the FastAPI + WebSocket engine. |
| `curl http://127.0.0.1:7421/health` | Liveness probe — returns `{status, llm_provider, llm_model}`. |
| HTTP `POST /api/score`, `/api/parse-resume`, `/api/extract-style`; `GET/PUT /api/settings` | Read-only / one-shot routes mirroring the CLI commands. |
| WebSocket `/api/ws/run`, `/api/ws/bootstrap` | Interactive flows — server emits `confirm` / `choose` / `text` / `render_proposal` / `node_event` etc.; client replies with `{type:"reply", value:...}`. |

### Desktop app (`pnpm tauri:dev` from `desktop/`)

Every CLI command has a screen counterpart. Navigate via the left rail or the `cmd/ctrl+K` palette.

### Quality

| Command | Description |
|---------|-------------|
| `uv run pytest` | Run tests (344 currently) |
| `uv run ruff check src/ tests/` | Lint |
| `uv run ruff format src/ tests/` | Format |
| `uv run mypy src/` | Type check (strict) |
| `cd desktop && pnpm typecheck` | TypeScript strict check |
| `cd desktop && pnpm build` | Vite production build |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider: `openai`, `anthropic`, `google`, `openrouter` |
| `LLM_MODEL` | `gpt-4o` | Model name (provider-specific) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `GOOGLE_API_KEY` | — | Google AI API key |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ATS_SKIP_THRESHOLD` | `0.9` | Skip optimization when composite ATS is at-or-above AND every sub-dimension is healthy (#042). |
| `ENRICH_THRESHOLD` | `6` | Below this kept+reworded item count, `run` offers an enrichment session. |
| `RESUME_MAX_ITERATIONS` | `3` | Cap on the #040 approval loop before the "continue anyway?" prompt fires. |
| `ATS_WEIGHT_HARD` / `_SOFT` / `_STRUCTURAL` / `_TITLE` / `_MEASURABLE` / `_TONE` | `0.40 / 0.20 / 0.15 / 0.10 / 0.10 / 0.05` | #042 ATSReport composite weights — sum to 1.0 by default. |
| `RESUME_STYLE_PATH` | — | Path to a StyleTemplate YAML; overridden by `run --style <path>`. |
| `RESUME_TEMPLATE` | `default` | PDF render template (`default` only today). |

The desktop app's Settings screen exposes every variable above as a form (API keys arrive masked; type a new value to replace). Writes persist to `.env` in the project root.

## Guides

- [How to Use](docs/guides/usage.md) — end-to-end walkthrough of the CLI and the desktop app.
- [How to Develop](docs/guides/development.md) — local setup, LangGraph concepts, testing, adding nodes / tools / screens.
- [How to Deploy](docs/guides/deployment.md) — running the engine via Docker; building the Windows desktop installer.
- [Iterative tailor with approval](docs/guides/iterative-tailor-approval.md) — how the default `run` loop works (CLI specifics).
- [Architecture](docs/architecture.md) — system diagram, agent flow, conditional routing, desktop GUI layer.

## Roadmap

Issue specs live in [`docs/issues/`](docs/issues/) — `NNN-name.md` files indexed in [`docs/issues/README.md`](docs/issues/README.md). The desktop GUI shipped as Phase 8 (specs [#043-#048](docs/issues/043-fastapi-server-for-desktop-gui.md), GitHub issues [#84-#89](https://github.com/takeshi-su57/resume-operator/issues/84)).

## AI Engineering

This project uses an AI engineering framework for structured development. See [AI_ENGINEERING.md](AI_ENGINEERING.md) for details.
