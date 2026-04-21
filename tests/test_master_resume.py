"""Tests for `tools.master_resume`."""

from __future__ import annotations

from pathlib import Path

import pytest

from resume_operator.state import ResumeData, ResumeMaster
from resume_operator.tools.master_resume import (
    MasterResumeError,
    load_master,
    resume_data_to_master,
    save_master,
)


class TestLoadMaster:
    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "master.yaml"
        path.write_text(
            "name: Jane Smith\n"
            "email: jane@example.com\n"
            "experience:\n"
            "  - id: exp-1\n"
            "    role: Senior Engineer\n"
            "    company: Acme\n"
            "    bullets:\n"
            "      - id: exp-1-b1\n"
            "        text: Shipped things\n"
            "skills:\n"
            "  - Go\n"
            "  - Python\n",
            encoding="utf-8",
        )
        master = load_master(path)
        assert master.name == "Jane Smith"
        assert master.email == "jane@example.com"
        assert len(master.experience) == 1
        assert master.experience[0].id == "exp-1"
        assert master.experience[0].bullets[0].text == "Shipped things"
        assert master.skills == ["Go", "Python"]

    def test_raises_when_missing(self, tmp_path: Path) -> None:
        with pytest.raises(MasterResumeError, match="not found"):
            load_master(tmp_path / "nope.yaml")

    def test_raises_on_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        with pytest.raises(MasterResumeError, match="empty"):
            load_master(path)

    def test_raises_on_non_mapping_root(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- just a list\n", encoding="utf-8")
        with pytest.raises(MasterResumeError, match="mapping"):
            load_master(path)

    def test_raises_on_schema_mismatch(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        # `experience` is a mapping instead of a list — schema violation.
        path.write_text("experience:\n  not: a-list\n", encoding="utf-8")
        with pytest.raises(MasterResumeError, match="schema"):
            load_master(path)


class TestSaveMaster:
    def test_roundtrip(self, tmp_path: Path) -> None:
        master = ResumeMaster(name="A", email="a@b", skills=["Go"])
        out = tmp_path / "nested" / "master.yaml"
        save_master(master, out)
        assert out.exists()
        loaded = load_master(out)
        assert loaded.name == "A"
        assert loaded.skills == ["Go"]


class TestResumeDataToMaster:
    def test_assigns_stable_ids(self) -> None:
        resume = ResumeData(
            name="X",
            experience=[
                {
                    "role": "Eng",
                    "company": "Acme",
                    "description": "- did thing one\n- did thing two",
                },
                {"role": "Jr Eng", "company": "Widget", "description": "- only one"},
            ],
            education=[{"degree": "BS CS", "school": "State"}],
            skills=["Go"],
        )
        master = resume_data_to_master(resume)
        assert master.name == "X"
        assert [e.id for e in master.experience] == ["exp-1", "exp-2"]
        assert [b.id for b in master.experience[0].bullets] == ["exp-1-b1", "exp-1-b2"]
        assert master.experience[0].bullets[0].text == "did thing one"
        assert master.education[0].id == "edu-1"
        assert master.skills == ["Go"]

    def test_handles_blank_description(self) -> None:
        resume = ResumeData(experience=[{"role": "Eng", "company": "Acme"}])
        master = resume_data_to_master(resume)
        assert master.experience[0].bullets == []
