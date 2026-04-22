"""Tests for `tools.source_index`.

The index is the tailor's fabrication-guard input — it has to keep producing
stable `master:skill:<name>` IDs regardless of whether skills on the master
are flat or categorised (#68).
"""

from __future__ import annotations

from resume_operator.state import (
    EducationEntry,
    ExperienceBullet,
    ExperienceEntry,
    FactsBank,
    ResumeMaster,
    SkillGroup,
)
from resume_operator.tools.source_index import build_source_index


def _minimal_master(**overrides: object) -> ResumeMaster:
    base = ResumeMaster(
        name="Jane",
        experience=[
            ExperienceEntry(
                id="exp-1",
                role="Engineer",
                company="Acme",
                bullets=[ExperienceBullet(id="exp-1-b1", text="Did things")],
            )
        ],
        education=[EducationEntry(id="edu-1", degree="BS CS", school="State U")],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class TestSkillIndexing:
    def test_flat_skills_indexed(self) -> None:
        master = _minimal_master(skills=["Python", "AWS"])
        idx = build_source_index(master, None)
        assert "master:skill:Python" in idx
        assert "master:skill:AWS" in idx

    def test_skill_groups_flatten_to_same_ids(self) -> None:
        """Categorised skills still index as `master:skill:<name>` — the tailor
        shouldn't need to know whether the master is grouped or flat."""
        master = _minimal_master(
            skill_groups=[
                SkillGroup(category="Languages", items=["Python", "Go"]),
                SkillGroup(category="Cloud", items=["AWS", "Docker"]),
            ]
        )
        idx = build_source_index(master, None)
        for name in ("Python", "Go", "AWS", "Docker"):
            assert f"master:skill:{name}" in idx

    def test_flat_and_grouped_dedupe(self) -> None:
        """A skill present in both `skills` and `skill_groups` should only index
        once — same ID, same entry."""
        master = _minimal_master(
            skills=["Python", "Go"],
            skill_groups=[SkillGroup(category="Languages", items=["Python", "Rust"])],
        )
        idx = build_source_index(master, None)
        # Three unique skills total: Python, Go (flat) + Rust (group).
        skill_ids = [i for i in idx.entries if i.startswith("master:skill:")]
        assert sorted(skill_ids) == [
            "master:skill:Go",
            "master:skill:Python",
            "master:skill:Rust",
        ]


class TestFactsBankPassthrough:
    def test_facts_skills_still_indexed_separately(self) -> None:
        """facts_bank skills continue to index under `facts:skill:<name>` —
        unchanged by #68."""
        master = _minimal_master(skills=["Python"])
        facts = FactsBank(skills_beyond_master=["Docker"])
        idx = build_source_index(master, facts)
        assert "master:skill:Python" in idx
        assert "facts:skill:Docker" in idx
