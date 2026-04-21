"""Tests for `tools.facts_bank`."""

from __future__ import annotations

from pathlib import Path

import pytest

from resume_operator.tools.facts_bank import FactsBankError, load_facts


class TestLoadFacts:
    def test_returns_empty_when_path_is_none(self) -> None:
        bank = load_facts(None)
        assert bank.projects == []
        assert bank.extra_bullets == []
        assert bank.skills_beyond_master == []

    def test_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        bank = load_facts(tmp_path / "nope.yaml")
        assert bank.projects == []

    def test_returns_empty_when_file_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        bank = load_facts(path)
        assert bank.projects == []

    def test_loads_valid_bank(self, tmp_path: Path) -> None:
        path = tmp_path / "facts.yaml"
        path.write_text(
            "projects:\n"
            "  - id: proj-1\n"
            "    text: Built a pipeline\n"
            "extra_bullets:\n"
            "  - id: extra-1\n"
            "    role_id: exp-1\n"
            "    text: Did a thing\n"
            "skills_beyond_master: [Docker, Terraform]\n",
            encoding="utf-8",
        )
        bank = load_facts(path)
        assert len(bank.projects) == 1
        assert bank.projects[0].id == "proj-1"
        assert bank.extra_bullets[0].role_id == "exp-1"
        assert bank.skills_beyond_master == ["Docker", "Terraform"]

    def test_raises_on_non_mapping(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- just a list\n", encoding="utf-8")
        with pytest.raises(FactsBankError, match="mapping"):
            load_facts(path)

    def test_raises_on_schema_mismatch(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("projects:\n  - not-a-mapping\n", encoding="utf-8")
        with pytest.raises(FactsBankError, match="schema"):
            load_facts(path)
