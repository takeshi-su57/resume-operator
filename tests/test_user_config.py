"""Tests for `tools.user_config` and the `/api/config` route."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lucky_resume.config import get_settings
from lucky_resume.server.app import create_app
from lucky_resume.tools.user_config import (
    config_file_path,
    read_config,
    write_config,
)


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the env-file path (and therefore the sibling config.json) at
    a per-test temp directory so writes don't clobber the developer's
    real config."""
    monkeypatch.setenv("RESUME_OPERATOR_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    return tmp_path


class TestReadConfig:
    def test_returns_empty_when_missing(self, isolated_config: Path) -> None:
        assert read_config() == {}

    def test_returns_empty_when_file_is_blank(self, isolated_config: Path) -> None:
        config_file_path().write_text("")
        assert read_config() == {}

    def test_skips_malformed_json_safely(self, isolated_config: Path) -> None:
        config_file_path().write_text("{not json")
        # Defensive: bad JSON shouldn't propagate to callers.
        assert read_config() == {}

    def test_skips_non_object_top_level(self, isolated_config: Path) -> None:
        config_file_path().write_text('["arrays", "are", "rejected"]')
        assert read_config() == {}


class TestWriteConfig:
    def test_creates_file_on_first_write(self, isolated_config: Path) -> None:
        result = write_config({"history": {"bootstrap": []}})
        assert result == {"history": {"bootstrap": []}}
        assert config_file_path().exists()

    def test_deep_merges_object_branches(self, isolated_config: Path) -> None:
        write_config({"history": {"bootstrap": [{"source": "a", "output": "b", "at": 1}]}})
        write_config({"history": {"extract-style": [{"source": "c", "output": "d", "at": 2}]}})
        merged = read_config()
        # Both branches survive; the second write didn't clobber the first.
        assert "bootstrap" in merged["history"]
        assert "extract-style" in merged["history"]

    def test_replaces_arrays_wholesale(self, isolated_config: Path) -> None:
        write_config({"history": {"bootstrap": [{"source": "a", "output": "b", "at": 1}]}})
        write_config({"history": {"bootstrap": []}})
        # Arrays are not merged; the empty replacement wins.
        assert read_config()["history"]["bootstrap"] == []

    def test_preserves_unrelated_top_level_keys(self, isolated_config: Path) -> None:
        write_config({"alpha": 1, "history": {"bootstrap": []}})
        write_config({"history": {"bootstrap": [{"source": "x", "output": "y", "at": 1}]}})
        cfg = read_config()
        assert cfg["alpha"] == 1
        assert len(cfg["history"]["bootstrap"]) == 1


class TestConfigRoute:
    def test_get_returns_path_and_empty_config_initially(
        self, isolated_config: Path
    ) -> None:
        client = TestClient(create_app())
        resp = client.get("/api/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["config"] == {}
        # Sibling of the .env override — should resolve next to it.
        assert body["config_file_path"].endswith("config.json")
        assert str(isolated_config) in body["config_file_path"]

    def test_patch_round_trips_through_get(self, isolated_config: Path) -> None:
        client = TestClient(create_app())
        patch = {
            "data": {
                "history": {
                    "bootstrap": [{"source": "r.pdf", "output": "m.yaml", "at": 99}]
                }
            }
        }
        resp = client.patch("/api/config", json=patch)
        assert resp.status_code == 200
        assert resp.json()["config"]["history"]["bootstrap"][0]["source"] == "r.pdf"

        # GET sees the same shape after the PATCH.
        resp2 = client.get("/api/config")
        assert resp2.json()["config"]["history"]["bootstrap"][0]["at"] == 99
