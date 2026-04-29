"""Tests for the FastAPI + WebSocket server (Phase 1, #84).

Covers:

- Plain HTTP routes (health, settings, score, parse-resume, extract-style)
  with the underlying graph / node / tool calls mocked so no LLM fires.
- WebSocket session lifecycle — `/ws/run` drives an approval loop end to
  end with a scripted client that approves the first iteration.
- `WebSocketPrompter` unit tests for the message shapes the frontend
  will consume.

The goal is not coverage of the graph itself (that's already in the other
test files); it's coverage of the **new plumbing**: request/response
shapes, WS protocol, prompter ↔ websocket bridging.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lucky_resume.config import get_settings
from lucky_resume.server.app import create_app
from lucky_resume.state import (
    ATSScore,
    ResumeData,
    ResumeMaster,
    TailoredItem,
    TailoredResume,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Point each test at a temp .env so the settings write path doesn't
    # clobber the developer's real config. Honored by `paths.env_file_path`.
    monkeypatch.setenv("RESUME_OPERATOR_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
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
# /api/score
# --------------------------------------------------------------------------


class TestScore:
    def test_requires_master_or_resume(self, client: TestClient) -> None:
        resp = client.post("/api/score", json={"job": "job.txt"})
        assert resp.status_code == 422  # pydantic validator

    def test_rejects_nonexistent_paths(self, client: TestClient) -> None:
        resp = client.post(
            "/api/score", json={"master": "nope.yaml", "job": "also-nope.txt"}
        )
        assert resp.status_code == 400

    @patch("lucky_resume.server.routes.score.build_score_graph")
    def test_returns_ats_score(
        self, mock_build: MagicMock, client: TestClient, tmp_path: Path
    ) -> None:
        master = tmp_path / "m.yaml"
        master.write_text("name: Test\n")
        job = tmp_path / "j.txt"
        job.write_text("Backend role.")

        graph = MagicMock()
        graph.invoke.return_value = {
            "ats_score": ATSScore(score=0.82, reasoning="looks good"),
            "errors": [],
        }
        mock_build.return_value = graph

        resp = client.post(
            "/api/score", json={"master": str(master), "job": str(job)}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ats_score"]["score"] == pytest.approx(0.82)
        assert body["errors"] == []
        graph.invoke.assert_called_once()


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
# /ws/run — end-to-end websocket happy path
# --------------------------------------------------------------------------


class TestRunWebsocket:
    @patch("lucky_resume.server.routes.run.build_finalize_graph")
    @patch("lucky_resume.server.routes.run.build_tailor_graph")
    def test_accept_on_first_iteration(
        self,
        mock_tailor: MagicMock,
        mock_finalize: MagicMock,
        client: TestClient,
        tmp_path: Path,
    ) -> None:
        """Full happy path: client sends start → server renders iteration
        header + asks confirm → client approves → finalize runs → done."""
        master = tmp_path / "m.yaml"
        master.write_text("name: X\n")
        job = tmp_path / "j.txt"
        job.write_text("role text")

        tailor_result = {
            "ats_score": ATSScore(score=0.9, reasoning=""),
            "tailored_resume": TailoredResume(
                items=[TailoredItem(source_id="master:exp-1-b1", action="keep")]
            ),
            "master": ResumeMaster(name="X"),
            "errors": [],
        }
        tailor = MagicMock()
        tailor.invoke.return_value = tailor_result
        mock_tailor.return_value = tailor

        finalize = MagicMock()
        finalize.invoke.return_value = {**tailor_result, "output_path": "out.pdf"}
        mock_finalize.return_value = finalize

        with client.websocket_connect("/api/ws/run") as ws:
            ws.send_json(
                {
                    "type": "start",
                    "params": {
                        "master": str(master),
                        "job": str(job),
                        "no_enrich": True,
                        "no_approve": False,
                        "max_iter": 3,
                    },
                }
            )
            # The flow runs asynchronously — we consume server messages
            # until we hit a `confirm`, answer yes, and then wait for done.
            got_confirm = False
            got_done = False
            for _ in range(30):  # generous upper bound
                msg = ws.receive_json()
                if msg["type"] == "confirm":
                    ws.send_json({"type": "reply", "value": True})
                    got_confirm = True
                elif msg["type"] == "done":
                    got_done = True
                    break
                elif msg["type"] == "error":
                    pytest.fail(f"server errored: {msg.get('message')}")
            assert got_confirm, "expected at least one confirm prompt"
            assert got_done, "expected a done message"


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
