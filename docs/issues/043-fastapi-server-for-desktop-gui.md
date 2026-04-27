# [Feature]: FastAPI + WebSocket server wrapping the tailor graph — Phase 1 of desktop GUI

GitHub issue: [#84](https://github.com/takeshi-su57/resume-operator/issues/84) · PR [#90](https://github.com/takeshi-su57/resume-operator/pull/90)

## Description

Today's `resume-operator` is a Rich-heavy CLI: the iterative approval loop (#040) and the enrichment interview (#033) both block on `rich.prompt.Prompt.ask`. A terminal flattens what are actually rich, back-and-forth decisions — the user stares at a long proposal `Panel`, types `y`/`n`/`f`, and can't see the diff side-by-side with the rationale, ATS score breakdown, or the rest of the tailored resume. This issue is the first step of a six-phase effort to turn resume-operator into a Tauri desktop app with a pro/dense Linear-style UI.

## Motivation

The interactive flows are the highest-value moments in the tool but the lowest-fidelity in the CLI. Every other phase (Tauri shell, Run workspace, enrichment cards, packaging) needs a localhost server it can drive. This issue produces that server while keeping the CLI as a peer surface — both invoke the same compiled LangGraph and the same flows behind a `Prompter` seam.

## Target State

### Phase 0 prerequisite (bundled in this PR)

Introduces a `Prompter` protocol with a `RichPrompter` CLI implementation and moves the approval / enrichment orchestration behind that seam into `src/resume_operator/flows/`. Adds a `NodeEventEmitter` scaffolding (no-op until a sink binds — the server does that). Zero behavior change for the CLI.

### Phase 1 server

Running `uv run resume-operator-server --port 7421` boots a FastAPI app with:

- `POST /api/score` — master + JD → multi-dim `ATSReport` (#042) JSON
- `POST /api/parse-resume` — PDF → `ResumeData` JSON
- `POST /api/extract-style` — .docx → `StyleTemplate` YAML (#037)
- `GET /api/settings` / `PUT /api/settings` — read with API keys masked, write persists to `.env`
- `WS /api/ws/run` — full pipeline (tailor → optional enrich → optional approval loop → finalize)
- `WS /api/ws/bootstrap` — PDF parse → interactive interview → master YAML write
- `GET /health` — sidecar liveness probe for the Tauri shell

Interactive sessions get a WebSocket per route. The `WebSocketPrompter` emits JSON messages for each `render_*` / `confirm` / `choose` / `text` / `status` call on the `Prompter` protocol, and awaits JSON replies carrying user decisions. Structured node events land on the same socket via the `NodeEventEmitter` sink — so a frontend can render a live node timeline.

The CLI is unchanged: `uv run python -m resume_operator run --master ... --job ...` still works exactly as before. The server is a peer surface, not a replacement. Both paths run the same `build_score_graph()` / `build_tailor_graph()` / `build_finalize_graph()` — no duplicated business logic.

### Bridge mechanics

- `WebSocketPrompter._send` schedules `await ws.send_json(...)` on the server event loop via `asyncio.run_coroutine_threadsafe` — called from the worker thread.
- `WebSocketPrompter._recv` blocks on `queue.Queue.get()` for a client reply — also called from the worker thread.
- `session_runner.run_flow_over_ws` runs the blocking flow in `asyncio.to_thread`, with the route's coroutine pumping client messages into the prompter's inbox.
- A clean disconnect raises `PrompterDisconnectedError` inside the worker thread so the flow returns early instead of deadlocking on an unanswered prompt.

## Success Metrics

- `curl -X POST http://localhost:7421/api/score -F master=@data/master_resume.yaml -F job=@input/job.txt` returns a JSON `ATSReport` matching the CLI's table output dimension-for-dimension.
- A scripted WebSocket client can drive a full approval loop: receive `render_proposal` → send `{"choice": "y"}` → receive next proposal → …, with `facts_bank.yaml` on disk updated identically to the CLI's behavior.
- All existing pytest + ruff + mypy gates pass, plus new server-route tests mocking the graph invocation.

## Key Files

- `src/resume_operator/prompter.py` (NEW) — `Prompter` protocol.
- `src/resume_operator/prompters/rich_prompter.py` (NEW) — CLI impl.
- `src/resume_operator/flows/{approval,enrich}.py` (NEW) — orchestration extracted from `main.py`.
- `src/resume_operator/events.py` (NEW) — `NodeEventEmitter` ContextVar + `node_span` context manager.
- `src/resume_operator/server/{app,main,session_runner,ws_prompter}.py` (NEW).
- `src/resume_operator/server/routes/{health,settings,score,parse_resume,extract_style,bootstrap,run}.py` (NEW).
- `src/resume_operator/main.py` — refactor `_run_approval_loop` / `_run_auto_enrich` to call `flows/*` with a `RichPrompter`.
- `src/resume_operator/tools/{approval_flow,enrich,bootstrap_interview}.py` — swap `console: Console | None` parameters for `prompter: Prompter`.
- `src/resume_operator/nodes/*.py` — wrap node bodies in `with node_span(...)` for live timeline events.
- `pyproject.toml` — `fastapi`, `uvicorn[standard]`, `python-multipart`, `websockets`. `resume-operator-server` console script.
- `tests/test_server.py` (NEW) — HTTP route tests + WS lifecycle test + `WebSocketPrompter` unit tests.

## Dependencies

- **#040** (iterative approval loop) — the highest-value flow this surface needs to expose.
- **#033/#034** (enrichment interview) — the second interactive flow.
- **#042** (multi-dim ATS report) — the response shape `/api/score` returns.

## Out of Scope

- Tauri frontend (Phase 2, #044).
- Multi-window / multi-session — Phase 1 supports one client per WS endpoint; the server already keys on the WS connection so multi-session is a small extension when needed.
- Authentication / authorization — server binds to `127.0.0.1` only; loopback is the only access path.

## Labels

`enhancement`, `priority:high`
