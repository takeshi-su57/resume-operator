"""Tests for `tools.output_dir`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from resume_operator.tools.output_dir import resolve_output_dir


class TestResolveOutputDir:
    def test_uses_company_when_provided(self, tmp_path: Path) -> None:
        out = resolve_output_dir(
            parent=tmp_path,
            jd_path=None,
            jd_text="job text",
            company="Acme Corp",
            today=date(2026, 4, 21),
        )
        assert out.name == "2026-04-21_acme-corp"
        assert out.exists()

    def test_falls_back_to_jd_filename_stem(self, tmp_path: Path) -> None:
        jd = tmp_path / "Senior Backend at BigCo.txt"
        jd.write_text("text", encoding="utf-8")
        out = resolve_output_dir(
            parent=tmp_path / "out", jd_path=jd, jd_text="text", today=date(2026, 4, 21)
        )
        assert out.name == "2026-04-21_senior-backend-at-bigco"

    def test_falls_back_to_jd_text_hash(self, tmp_path: Path) -> None:
        out = resolve_output_dir(
            parent=tmp_path,
            jd_path=None,
            jd_text="some unique job text",
            today=date(2026, 4, 21),
        )
        assert out.name.startswith("2026-04-21_jd-")
        # Hash suffix is 8 hex chars after `jd-`.
        suffix = out.name.removeprefix("2026-04-21_jd-")
        assert len(suffix) == 8

    def test_handles_collisions_with_numeric_suffix(self, tmp_path: Path) -> None:
        first = resolve_output_dir(
            parent=tmp_path, jd_path=None, jd_text="x", company="Acme", today=date(2026, 4, 21)
        )
        second = resolve_output_dir(
            parent=tmp_path, jd_path=None, jd_text="x", company="Acme", today=date(2026, 4, 21)
        )
        third = resolve_output_dir(
            parent=tmp_path, jd_path=None, jd_text="x", company="Acme", today=date(2026, 4, 21)
        )
        assert first.name == "2026-04-21_acme"
        assert second.name == "2026-04-21_acme-2"
        assert third.name == "2026-04-21_acme-3"

    def test_creates_parent_when_missing(self, tmp_path: Path) -> None:
        parent = tmp_path / "deep" / "nested" / "applications"
        out = resolve_output_dir(
            parent=parent, jd_path=None, jd_text="x", company="Acme", today=date(2026, 4, 21)
        )
        assert out.parent == parent
        assert out.exists()

    def test_default_parent_when_none(self, tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # Run inside tmp_path so the default "data/applications/" lands there.
        monkeypatch.chdir(tmp_path)
        out = resolve_output_dir(
            parent=None, jd_path=None, jd_text="x", company="Acme", today=date(2026, 4, 21)
        )
        # The default is the relative path `data/applications` (resolved against the cwd).
        assert out == Path("data/applications") / "2026-04-21_acme"
        assert (tmp_path / "data" / "applications" / "2026-04-21_acme").exists()
