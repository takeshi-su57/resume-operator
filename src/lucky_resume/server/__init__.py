"""FastAPI + WebSocket server wrapping the lucky-resume graph.

The server is a peer surface to the CLI — both invoke the same compiled
LangGraph (`build_score_graph`, `build_tailor_graph`, `build_finalize_graph`)
and the same interactive flows (`flows.approval`, `flows.enrich`). The
only thing that changes between them is which `Prompter` drives the
blocking user-decision calls: `RichPrompter` for the CLI,
`WebSocketPrompter` for the desktop GUI.

Entry point: `lucky-resume-server` (see `pyproject.toml`).
"""
