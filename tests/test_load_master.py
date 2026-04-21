"""Tests for the `load_master` node."""

from __future__ import annotations

from pathlib import Path

from resume_operator.nodes.load_master import load_master_node
from resume_operator.state import ResumeOptimizerState

EXAMPLE_YAML = """\
name: Jane Smith
email: jane@example.com
experience:
  - id: exp-1
    role: Senior Engineer
    company: Acme
    bullets:
      - id: exp-1-b1
        text: Shipped things
skills: [Go, Python]
"""


def _write_master(path: Path, body: str = EXAMPLE_YAML) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


class TestLoadMasterNode:
    def test_populates_master_and_resume(self, tmp_path: Path) -> None:
        master_path = _write_master(tmp_path / "master.yaml")
        state = ResumeOptimizerState(master_path=str(master_path))
        result = load_master_node(state)

        assert "master" in result
        assert result["master"].name == "Jane Smith"

        # Downstream-compatible view populated.
        assert "resume" in result
        assert result["resume"].name == "Jane Smith"
        assert "- Shipped things" in result["resume"].experience[0]["description"]
        assert result["resume"].skills == ["Go", "Python"]

    def test_reads_job_description_from_path(self, tmp_path: Path) -> None:
        master_path = _write_master(tmp_path / "master.yaml")
        job_path = tmp_path / "job.txt"
        job_path.write_text("We need a senior Go engineer.", encoding="utf-8")

        state = ResumeOptimizerState(
            master_path=str(master_path), job_description_path=str(job_path)
        )
        result = load_master_node(state)

        assert "job_description" in result
        assert "senior Go engineer" in result["job_description"].raw_text

    def test_records_error_when_master_path_empty(self) -> None:
        state = ResumeOptimizerState()
        result = load_master_node(state)
        assert result["errors"]
        assert any("master_path is empty" in e for e in result["errors"])

    def test_records_error_when_yaml_missing(self, tmp_path: Path) -> None:
        state = ResumeOptimizerState(master_path=str(tmp_path / "nope.yaml"))
        result = load_master_node(state)
        assert result["errors"]
        assert any("not found" in e for e in result["errors"])

    def test_loads_optional_facts_bank(self, tmp_path: Path) -> None:
        master_path = _write_master(tmp_path / "master.yaml")
        facts_path = tmp_path / "facts.yaml"
        facts_path.write_text(
            "projects:\n  - id: proj-1\n    text: Built X\n",
            encoding="utf-8",
        )
        state = ResumeOptimizerState(master_path=str(master_path), facts_path=str(facts_path))
        result = load_master_node(state)

        assert "facts" in result
        assert len(result["facts"].projects) == 1
        assert result["facts"].projects[0].id == "proj-1"

    def test_missing_facts_bank_is_not_an_error(self, tmp_path: Path) -> None:
        master_path = _write_master(tmp_path / "master.yaml")
        state = ResumeOptimizerState(
            master_path=str(master_path), facts_path=str(tmp_path / "no-facts.yaml")
        )
        result = load_master_node(state)

        assert not result.get("errors"), result.get("errors")
        assert "facts" in result
        assert result["facts"].projects == []
