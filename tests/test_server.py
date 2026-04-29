"""Tests for the FastAPI + WebSocket server.

Covers:

- Plain HTTP routes (health, settings, parse-resume, extract-style)
  with the underlying graph / node / tool calls mocked so no LLM fires.
- Task registry CRUD + start endpoints (request validation, task_id
  shape). Full task lifecycle (start → run → completed) is covered by
  direct asyncio tests in `test_tasks.py` — Starlette's `TestClient`
  doesn't reliably progress `asyncio.create_task`-spawned background
  work between blocking sync requests, which makes end-to-end E2E
  tests against the registry flaky.
- `WebSocketPrompter` unit tests for the message shapes the bootstrap
  flow consumes.

The goal is not coverage of the graph itself (that's already in the
other test files); it's coverage of the plumbing: request/response
shapes, validation surface, prompter ↔ websocket bridging.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lucky_resume.config import get_settings
from lucky_resume.server.app import create_app
from lucky_resume.server.tasks.registry import get_registry
from lucky_resume.state import (
    ResumeData,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Point each test at a temp .env so the settings write path doesn't
    # clobber the developer's real config. Honored by `paths.env_file_path`.
    monkeypatch.setenv("RESUME_OPERATOR_ENV_FILE", str(tmp_path / ".env"))
    # Park task history under tmp_path so tests don't pollute the real
    # `%APPDATA%\\lucky-resume\\tasks\\` dir, and the lifecycle scan
    # starts each test against an empty history.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    # Drop any registry state leaking across tests.
    for handle in list(get_registry().all()):
        get_registry().drop(handle.task.id)
    return TestClient(create_app())


# --------------------------------------------------------------------------
# /health
# --------------------------------------------------------------------------


class TestHealth:
    def test_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "llm_provider" in body
        assert "llm_model" in body


# --------------------------------------------------------------------------
# /api/settings
# --------------------------------------------------------------------------


class TestSettings:
    def test_get_masks_api_keys(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-abcdefghij1234567890")
        get_settings.cache_clear()
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        body = resp.json()
        # Masked: should NOT contain the middle of the key.
        assert "abcdefghij" not in body["openai_api_key"]
        # But should still indicate the key is set (first/last chars visible).
        assert body["openai_api_key"].startswith("sk-p")
        assert body["openai_api_key"].endswith("7890")

    def test_put_persists_to_env_file(self, client: TestClient, tmp_path: Path) -> None:
        resp = client.put(
            "/api/settings",
            json={"llm_provider": "anthropic", "llm_model": "claude-sonnet-4-6"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["llm_provider"] == "anthropic"
        assert body["llm_model"] == "claude-sonnet-4-6"

        env_file = tmp_path / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "LLM_PROVIDER=anthropic" in content
        assert "LLM_MODEL=claude-sonnet-4-6" in content

    def test_put_empty_payload_is_noop(self, client: TestClient) -> None:
        resp = client.put("/api/settings", json={})
        assert resp.status_code == 200
        # Just round-trips the current values — no env file created.


# --------------------------------------------------------------------------
# /api/tasks — request validation + task_id shape
# --------------------------------------------------------------------------


class TestTaskStartEndpoints:
    """The start endpoints are thin — they validate input and return a task_id.

    Full lifecycle (queued → running → completed) is exercised in
    `test_tasks.py` against the registry directly, since `TestClient`
    doesn't reliably progress backgrounded `asyncio.create_task`s
    between blocking sync requests.
    """

    def test_score_requires_master_or_resume(self, client: TestClient) -> None:
        resp = client.post("/api/tasks/score", json={"job": "job.txt"})
        assert resp.status_code == 422

    def test_score_returns_task_id(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        master = tmp_path / "m.yaml"
        master.write_text("name: T\n")
        job = tmp_path / "j.txt"
        job.write_text("role")
        resp = client.post(
            "/api/tasks/score", json={"master": str(master), "job": str(job)}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "task_id" in body
        # Sortable id format: 13-digit ms timestamp + 8 hex chars.
        assert "-" in body["task_id"]

    def test_run_requires_job(self, client: TestClient) -> None:
        resp = client.post("/api/tasks/run", json={})
        assert resp.status_code == 422

    def test_run_returns_task_id(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        master = tmp_path / "m.yaml"
        master.write_text("name: T\n")
        job = tmp_path / "j.txt"
        job.write_text("role")
        resp = client.post(
            "/api/tasks/run",
            json={"master": str(master), "job": str(job), "no_approve": True},
        )
        assert resp.status_code == 200
        assert "task_id" in resp.json()

    def test_list_returns_persisted_tasks(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        master = tmp_path / "m.yaml"
        master.write_text("name: T\n")
        job = tmp_path / "j.txt"
        job.write_text("role")
        resp = client.post(
            "/api/tasks/score", json={"master": str(master), "job": str(job)}
        )
        task_id = resp.json()["task_id"]

        listed = client.get("/api/tasks").json()
        assert any(t["id"] == task_id for t in listed)

    def test_get_unknown_task_404(self, client: TestClient) -> None:
        resp = client.get("/api/tasks/nope-nope")
        assert resp.status_code == 404


# --------------------------------------------------------------------------
# /api/parse-resume
# --------------------------------------------------------------------------


class TestParseResumeRoute:
    def test_rejects_non_pdf(self, client: TestClient, tmp_path: Path) -> None:
        f = tmp_path / "not-a-pdf.txt"
        f.write_text("x")
        resp = client.post("/api/parse-resume", json={"resume": str(f)})
        assert resp.status_code == 400

    @patch("lucky_resume.server.routes.parse_resume.parse_resume_node")
    def test_returns_resume_data(
        self, mock_node: MagicMock, client: TestClient, tmp_path: Path
    ) -> None:
        resume = tmp_path / "resume.pdf"
        resume.write_bytes(b"%PDF-1.4 dummy")
        mock_node.return_value = {
            "resume": ResumeData(name="Jane", email="j@x.co", skills=["Python"]),
            "errors": [],
        }
        resp = client.post("/api/parse-resume", json={"resume": str(resume)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["resume"]["name"] == "Jane"
        assert "Python" in body["resume"]["skills"]


# --------------------------------------------------------------------------
# /api/extract-style
# --------------------------------------------------------------------------


class TestExtractStyleRoute:
    def test_rejects_non_docx(self, client: TestClient, tmp_path: Path) -> None:
        f = tmp_path / "not.docx.txt"
        f.write_text("x")
        resp = client.post("/api/extract-style", json={"source": str(f)})
        assert resp.status_code == 400

    @patch("lucky_resume.server.routes.extract_style.extract_style_from_docx")
    def test_returns_style_without_writing(
        self, mock_extract: MagicMock, client: TestClient, tmp_path: Path
    ) -> None:
        from lucky_resume.tools.style import StyleTemplate

        src = tmp_path / "ref.docx"
        src.write_bytes(b"dummy")
        mock_extract.return_value = StyleTemplate()

        resp = client.post("/api/extract-style", json={"source": str(src)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["written_to"] is None
        assert "style" in body




# --------------------------------------------------------------------------
# WebSocketPrompter unit tests — message shapes
# --------------------------------------------------------------------------


class TestWebSocketPrompterMessages:
    def test_confirm_message_shape(self) -> None:
        """`confirm` sends a `{type: confirm, ...}` payload and returns the
        reply's value. Uses a fake WebSocket to capture the outgoing
        message and inject the reply."""
        import asyncio

        sent: list[dict[str, Any]] = []

        class FakeWS:
            async def send_json(self, payload: dict[str, Any]) -> None:
                sent.append(payload)

        loop = asyncio.new_event_loop()

        async def _run() -> bool:
            from lucky_resume.server.ws_prompter import WebSocketPrompter

            p = WebSocketPrompter(FakeWS(), asyncio.get_running_loop())
            # Pre-load a reply so `_recv` doesn't block.
            p.deposit_reply({"type": "reply", "value": True})
            return await asyncio.to_thread(p.confirm, "accept?", default=False)

        try:
            result = loop.run_until_complete(_run())
        finally:
            loop.close()

        assert result is True
        assert sent == [{"type": "confirm", "message": "accept?", "default": False}]

    def test_render_proposal_serializes_pydantic_model(self) -> None:
        import asyncio

        from lucky_resume.state import Proposal

        sent: list[dict[str, Any]] = []

        class FakeWS:
            async def send_json(self, payload: dict[str, Any]) -> None:
                sent.append(payload)

        loop = asyncio.new_event_loop()

        async def _run() -> None:
            from lucky_resume.server.ws_prompter import WebSocketPrompter

            p = WebSocketPrompter(FakeWS(), asyncio.get_running_loop())
            proposal = Proposal(
                kind="rewrite_master",
                grounding_source_id="master:exp-1-b1",
                proposed_text="Polished bullet",
            )
            await asyncio.to_thread(p.render_proposal, proposal, index=1, total=3)

        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()

        assert len(sent) == 1
        msg = sent[0]
        assert msg["type"] == "render_proposal"
        assert msg["index"] == 1
        assert msg["total"] == 3
        assert msg["proposal"]["kind"] == "rewrite_master"
        assert msg["proposal"]["proposed_text"] == "Polished bullet"
