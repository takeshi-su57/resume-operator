# How to Develop

Guide for setting up, running, and contributing to resume-operator. The repo ships two surfaces (CLI and desktop app) over a shared engine — this guide covers both.

For the system architecture diagram and data flow, see [docs/architecture.md](../architecture.md). For end-user workflows, see [How to Use](usage.md).

## Prerequisites

| What | Why | How |
|---|---|---|
| Python 3.12+ | Engine runtime | [python.org](https://www.python.org/) |
| [uv](https://docs.astral.sh/uv/) | Python package manager | `pipx install uv` or `cargo install uv` |
| Node 20+ | Desktop frontend | [nodejs.org](https://nodejs.org/) |
| pnpm 9+ | Desktop package manager | `npm install -g pnpm` |
| Rust stable 1.85+ | Tauri 2 shell | `rustup update stable` |
| MSVC C++ tools (Windows) | Tauri's link.exe | Visual Studio Installer → Modify → "Desktop development with C++" |
| An LLM API key | All LLM calls | OpenAI / Anthropic / Google / OpenRouter |
| Git | Version control | — |

If you only intend to work on the engine (CLI + tests + server), Node / pnpm / Rust / MSVC are skippable. The desktop folder is independent.

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd resume-operator

# Engine — install Python deps + dev deps
uv sync --dev

# Configure environment
cp .env.example .env
# Edit .env — add your LLM API key

# Desktop frontend (optional — only if you'll work on the GUI)
cd desktop
pnpm install
cd ..
```

### Environment Variables

All engine configuration is via env vars loaded by Pydantic Settings in `src/resume_operator/config.py`. See `.env.example` for the full list:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM backend: `openai`, `anthropic`, `google`, or `openrouter` |
| `LLM_MODEL` | `gpt-4o` | Model name passed to the provider |
| `OPENAI_API_KEY` | — | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `GOOGLE_API_KEY` | — | Required if `LLM_PROVIDER=google` |
| `OPENROUTER_API_KEY` | — | Required if `LLM_PROVIDER=openrouter` |
| `LOG_LEVEL` | `INFO` | Python logging level |

You only need **one** API key — the one matching your chosen `LLM_PROVIDER`.

## Running the Engine

### CLI

```bash
# Full pipeline
uv run python -m resume_operator run --master data/master_resume.yaml --job input/job.txt

# Score only
uv run python -m resume_operator score --master data/master_resume.yaml --job input/job.txt

# Bootstrap a master from a PDF
uv run python -m resume_operator bootstrap --resume some-resume.pdf

# All commands
uv run python -m resume_operator --help
```

### Server

Dev binds to **127.0.0.1:7422** so it can coexist with an installed production build, which always uses 7421.

```bash
# Boot the FastAPI + WebSocket engine on the dev port
uv run lucky-resume-server --port 7422

# Hot-reload on code changes (dev only)
uv run lucky-resume-server --port 7422 --reload

# Liveness probe
curl http://127.0.0.1:7422/health
```

### Desktop app (dev mode)

```bash
# Terminal 1 — engine on the dev port
uv run lucky-resume-server --port 7422

# Terminal 2 — Tauri shell
cd desktop
pnpm tauri:dev
```

The Tauri window opens against Vite's `localhost:1420`; HTTP/WebSocket calls hit the engine on `127.0.0.1:7422` (`desktop/.env.development` sets `VITE_SERVER_PORT=7422`). Hot-reload on the React side is automatic; Rust shell rebuilds on save.

If you don't want Tauri (e.g. iterating only on screen layout), `pnpm dev` serves the React app at `localhost:1420` in a regular browser. The OS file dialog (`@tauri-apps/plugin-dialog`) silently no-ops in browser mode — type paths in instead.

## Engine Architecture (LangGraph + Prompter Seam)

If you're new to the codebase, here's how the moving pieces fit.

### StateGraph

The agent is a LangGraph `StateGraph` — a directed graph where:

- **State** (`ResumeOptimizerState` in `src/resume_operator/state.py`) flows through the graph
- **Nodes** are Python functions that read state and return updates (in `src/resume_operator/nodes/`)
- **Edges** define the execution order (linear + one conditional gate after `ats_score`)

Three graphs are assembled in `src/resume_operator/graph.py`:

- `build_score_graph()` — `load_master/parse_resume → ats_score`. Used by the `score` command.
- `build_tailor_graph()` — `load_master/parse_resume → ats_score → [conditional] → analyze_gaps → optimize_content → ats_score_tailored`. Used by `run` for the loop body.
- `build_finalize_graph()` — `generate_pdf → report_results`. Run once at the end of `run`.

Each `compile()` validates the graph and returns a runnable. `invoke()` runs it once and returns the resulting state dict.

### Node Pattern

Every node follows the same shape (one function per file in `src/resume_operator/nodes/`):

```python
# src/resume_operator/nodes/my_node.py
import logging
from typing import Any
from resume_operator.events import node_span
from resume_operator.state import ResumeOptimizerState

logger = logging.getLogger(__name__)

def my_node(state: ResumeOptimizerState) -> dict[str, Any]:
    with node_span("my_node"):
        return _my_node_body(state)

def _my_node_body(state: ResumeOptimizerState) -> dict[str, Any]:
    logger.info("my_node: starting")

    # 1. Read what you need from state
    data = state.some_field

    # 2. Do work (call tools, LLM, etc.)
    result = some_tool(data)

    # 3. Return ONLY the fields you're updating
    logger.info("my_node: completed — key_metric=%s", metric)
    return {"output_field": result}
```

Key rules:

- Wrap the body in `with node_span("name")` so the GUI's live timeline lights up. `node_span` is a context manager that emits `{phase: start}` / `{phase: end}` events through the active `EventSink`. CLI doesn't bind one — the calls are no-ops.
- Return a **dict**, not the full state — LangGraph merges it automatically.
- Call **tools** (`src/resume_operator/tools/`) for I/O; nodes never import external libs directly.
- Use **prompt templates** from `src/resume_operator/prompts/`, not inline strings.
- **Catch exceptions** and append to `state.errors` instead of crashing.
- **Log** entry/exit at INFO level (see `.claude/rules/logging.md`).

For complete examples, see `src/resume_operator/nodes/parse_resume.py` and `src/resume_operator/nodes/optimize_content.py`.

### The Prompter Seam

Interactive flows (the iterative approval loop, the auto-enrichment session, the bootstrap interview) used to live in `main.py` and call `rich.prompt.Prompt.ask` directly. Phase 0 of the desktop GUI effort extracted them behind a `Prompter` protocol so the same business logic serves both the CLI and the desktop app.

```python
# src/resume_operator/prompter.py — abridged
class Prompter(Protocol):
    def confirm(self, message: str, *, default: bool = False) -> bool: ...
    def choose(self, message: str, choices: list[str], *, default: str) -> str: ...
    def text(self, message: str, *, default: str = "") -> str: ...
    def render_proposal(self, p: Proposal, *, index: int, total: int) -> None: ...
    def render_question(self, q: Question, *, index: int, total: int) -> None: ...
    def render_polished(self, p: PolishedFactLLMOutput) -> None: ...
    def notice(self, message: str, *, style: str = "") -> None: ...
    def panel(self, message: str, *, title: str, style: str = "") -> None: ...
    def status(self, message: str) -> AbstractContextManager[None]: ...
```

Two implementations:

- **`prompters/rich_prompter.py`** — wraps Rich `Console` + `Prompt` + `Confirm` + `Status`. Used by the CLI.
- **`server/ws_prompter.py`** — emits JSON over a FastAPI WebSocket, awaits replies through a `queue.Queue` inbox bridged with `asyncio.run_coroutine_threadsafe`. Used by the server.

The flows in `src/resume_operator/flows/` (`run_approval_loop`, `run_auto_enrich`) and `src/resume_operator/tools/` (`run_approval_flow`, `run_interactive_session`, `run_interview`) take a `prompter: Prompter` argument and call the protocol methods. They don't know which surface they're driving.

### Why `node_span`?

The desktop Run screen shows a live node timeline that lights up as the graph progresses. The server route handlers bind a `WebSocketEventSink` via `events.bind_sink(...)` for the duration of a flow; any node wrapped in `with node_span("name")` emits `{node, phase, timestamp}` events the frontend renders.

CLI runs don't bind a sink, so the emit calls are effectively a `_current_sink.get()` returning `None` — zero cost.

## Adding a New Node

1. **Create the node file** — `src/resume_operator/nodes/my_node.py` with one public function following the pattern above.
2. **Export it** — Add the import to `src/resume_operator/nodes/__init__.py`:
   ```python
   from resume_operator.nodes.my_node import my_node
   ```
3. **Wire it into the graph** — Edit `src/resume_operator/graph.py`:
   ```python
   graph.add_node("my_node", my_node)
   graph.add_edge("previous_node", "my_node")
   graph.add_edge("my_node", "next_node")
   ```
4. **Add state fields** — If the node produces new data, add the corresponding Pydantic model and field to `src/resume_operator/state.py`.
5. **Write tests** — Create `tests/test_my_node.py`. Mock all tools (`get_llm`, `extract_text`, etc.) and use fixtures from `tests/conftest.py`.
6. **Update the desktop timeline** (optional) — If the node should show in the GUI's live timeline, add it to `NODE_LABELS` + `NODE_ORDER` in [`desktop/src/screens/run/node-timeline.tsx`](../../desktop/src/screens/run/node-timeline.tsx).
7. **Update docs** — Update `.claude/CLAUDE.md` (Repository Layout + Agent Flow) and `docs/architecture.md` (system diagram).

## Adding a New Tool

1. **Create the tool file** — `src/resume_operator/tools/my_tool.py`. Tools handle external I/O (files, APIs, LLMs). Keep them focused — one concern per file.
2. **Use it from nodes** — Import the tool in your node and call it. Nodes call tools; tools never call nodes.
3. **Update docs** — Update `.claude/rules/architecture.md` (Tools Layer table) and `.claude/CLAUDE.md` (Repository Layout).

## Adding a New CLI Command

1. **Add a Typer function** in `src/resume_operator/main.py`. Wire it to a graph (or a flow + prompter for interactive commands).
2. **Add a corresponding HTTP / WebSocket route** in `src/resume_operator/server/routes/<name>.py` so the desktop app can drive it. Register it in `src/resume_operator/server/app.py`.
3. **Test both** — `tests/test_main.py` for the CLI, `tests/test_server.py` for the route.

## Adding a New Desktop Screen

```bash
cd desktop
```

1. **Create the screen** — `src/screens/<name>.tsx`. Read from `src/lib/api.ts` (HTTP) or `src/lib/ws.ts` (WebSocket); keep view-state in `useState` or a screen-specific zustand store.
2. **Register the route** in `src/App.tsx`:
   ```tsx
   <Route path="/my-screen" element={<MyScreen />} />
   ```
3. **Add a nav entry** in `src/components/nav-rail.tsx` and a command in `src/components/command-palette.tsx`.
4. **For interactive WebSocket flows**, model after `src/screens/run/use-run-controller.ts` — wire `useFlowSocket` to a zustand store, dispatch incoming `ServerMessage`s into store mutations, expose action methods that call `controller.send({type:"reply", value:...})`.
5. **For HTTP-only flows**, add a `useMutation` hook in `src/lib/api.ts` and consume it from the screen.
6. **Match the aesthetic** — Linear-style: monospace body (JetBrains Mono), single accent color (cyan-400), hairline borders (`#27272A` on `#161618`), compact rows, kbd hints on every keyboard-driven action.

## Testing

```bash
# Engine — pytest
uv run pytest                         # full suite (344 tests)
uv run pytest tests/test_state.py     # one file
uv run pytest -v                      # verbose
uv run coverage run -m pytest && uv run coverage report

# Engine — gates
uv run ruff check src/ tests/         # lint
uv run ruff format src/ tests/        # format
uv run mypy src/                      # type check (strict)

# Desktop — TypeScript + Vite
cd desktop
pnpm typecheck                        # strict TS
pnpm build                            # production build
```

### Engine Mocking Pattern

All external I/O must be mocked. Patch at the **call site**, not the definition:

```python
from unittest.mock import patch, MagicMock

@patch("resume_operator.nodes.my_node.get_llm")
@patch("resume_operator.nodes.my_node.extract_text")
def test_my_node(mock_extract, mock_get_llm):
    mock_extract.return_value = "Jane Smith\njane@example.com\n..."

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MyLLMOutput(name="Jane")
    mock_get_llm.return_value = mock_llm

    state = ResumeOptimizerState(resume_path="test.pdf")
    result = my_node(state)

    assert "output_field" in result
```

For interactive flows, inject a silent `RichPrompter`:

```python
from rich.console import Console
from resume_operator.prompters import RichPrompter

def _silent_prompter() -> RichPrompter:
    import io
    return RichPrompter(Console(file=io.StringIO(), force_terminal=False))

# Patch rich.prompt.Prompt.ask to script the user's keystrokes
with patch("rich.prompt.Prompt.ask", side_effect=["y", "feedback", "y"]):
    outcome = run_approval_flow(state, [proposal], revise_fn=mock_revise,
                                prompter=_silent_prompter())
```

For the server, `tests/test_server.py` uses FastAPI's `TestClient` — mock the underlying graph / nodes / tools, then drive HTTP via `client.post(...)` or WebSocket via `client.websocket_connect(...)`.

### Fixtures (in `tests/conftest.py`)

- `sample_resume` — `ResumeData` with realistic fields
- `sample_master` — `ResumeMaster` populated for the senior-format
- `sample_job` — `JobDescription` with requirements and keywords
- `sample_state` — Full `ResumeOptimizerState` with resume + job + analysis populated

For complete working test examples, see `tests/test_parse_resume.py` (node-level), `tests/test_iterative_loop.py` (flow-level), and `tests/test_server.py` (HTTP/WS).

## Project Conventions

- **Commits**: `type(scope): description` — see [`.claude/rules/git-commit.md`](../../.claude/rules/git-commit.md). Each commit compiles independently.
- **Files**: snake_case for files, PascalCase for classes
- **Types**: strict mypy on the engine, strict TypeScript on the desktop
- **Config**: env vars via `src/resume_operator/config.py`, never hardcode
- **Logging**: use `logging.getLogger(__name__)`, never `print()` — see [`.claude/rules/logging.md`](../../.claude/rules/logging.md)
- **Security**: never commit API keys or personal data — see [`.claude/rules/security.md`](../../.claude/rules/security.md)
- **PR stack**: phased work goes through stacked PRs — base each branch off the previous phase's branch; each PR closes its corresponding `docs/issues/NNN-*.md` spec.

## Key Files Reference

### Engine

| File | Purpose |
|------|---------|
| `src/resume_operator/main.py` | CLI entry point (Typer app) |
| `src/resume_operator/config.py` | Pydantic Settings — env var bindings |
| `src/resume_operator/state.py` | `ResumeOptimizerState` — central data contract |
| `src/resume_operator/graph.py` | LangGraph StateGraph assembly |
| `src/resume_operator/events.py` | `NodeEventEmitter` ContextVar + `node_span` |
| `src/resume_operator/prompter.py` | `Prompter` protocol |
| `src/resume_operator/prompters/rich_prompter.py` | CLI `Prompter` impl |
| `src/resume_operator/flows/` | Approval loop + auto-enrich orchestration |
| `src/resume_operator/nodes/` | One node function per file |
| `src/resume_operator/tools/` | I/O utilities (PDF, LLM, YAML, approval flow, enrich, bootstrap interview) |
| `src/resume_operator/prompts/` | LLM prompt templates as string constants |
| `src/resume_operator/server/` | FastAPI app + WebSocket prompter + routes |
| `tests/conftest.py` | Shared pytest fixtures |
| `.env.example` | Environment variable template |

### Desktop

| File | Purpose |
|------|---------|
| `desktop/package.json` | JS deps + scripts (`tauri:dev`, `tauri:build`, `typecheck`, `build`) |
| `desktop/vite.config.ts` | Vite + Tauri integration (port 1420 locked) |
| `desktop/tailwind.config.ts` | Linear-style theme tokens |
| `desktop/src/lib/api.ts` | HTTP client + TanStack Query hooks |
| `desktop/src/lib/ws.ts` | `useFlowSocket` hook for interactive flows |
| `desktop/src/lib/events.ts` | TS types mirroring `server/ws_prompter.py` |
| `desktop/src/state/run-session.ts` | zustand store for the Run screen |
| `desktop/src/screens/run/use-run-controller.ts` | Wires `useFlowSocket` to the store |
| `desktop/src/screens/run/workspace.tsx` | Three-pane orchestrator |
| `desktop/src-tauri/src/lib.rs` | Sidecar lifecycle (Phase 6) |
| `desktop/src-tauri/tauri.conf.json` | Window + bundle config |

### Build / packaging

| File | Purpose |
|------|---------|
| `pyinstaller/resume_operator_server.spec` | PyInstaller spec for the sidecar |
| `pyinstaller/build.py` | Bundle + smoke-test + install into `desktop/src-tauri/binaries/` |
| `desktop/scripts/release.ps1` | One-shot Windows release pipeline |

### Documentation

| File | Purpose |
|------|---------|
| [`docs/architecture.md`](../architecture.md) | System diagram + agent flow + desktop GUI layer |
| [`docs/guides/usage.md`](usage.md) | End-user walkthrough (CLI + desktop) |
| [`docs/guides/deployment.md`](deployment.md) | Docker + Windows installer build |
| [`docs/guides/iterative-tailor-approval.md`](iterative-tailor-approval.md) | Approval loop deep-dive |
| [`docs/issues/`](../issues/) | Issue specs (NNN-name.md), indexed in `README.md` |
