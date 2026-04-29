"""Tests for `tools.source_index`.

The index is the tailor's fabrication-guard input — it has to keep producing
stable `master:skill:<name>` IDs regardless of whether skills on the master
are flat or categorised (#68).
"""

from __future__ import annotations

from lucky_resume.state import (
    EducationEntry,
    ExperienceBullet,
    ExperienceEntry,
    FactItem,
    FactsBank,
    ResumeMaster,
    SkillGroup,
)
from lucky_resume.tools.source_index import build_source_index


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


class TestOverrides:
    """#78: facts-bank items with `overrides: master:...` shadow the master entry
    so the tailor sees exactly one version per thought."""

    def test_override_hides_master_bullet(self) -> None:
        master = _minimal_master()  # has master:exp-1-b1 "Did things"
        facts = FactsBank(
            extra_bullets=[
                FactItem(
                    id="enrich-1",
                    text="Did things with Kubernetes at scale",
                    overrides="master:exp-1-b1",
                )
            ]
        )
        idx = build_source_index(master, facts)
        assert "master:exp-1-b1" not in idx
        # The facts entry itself is still present under its own id.
        assert "facts:enrich-1" in idx
        assert idx.get("facts:enrich-1").text == "Did things with Kubernetes at scale"

    def test_fact_without_override_leaves_master_alone(self) -> None:
        """The presence of a facts bank doesn't suppress anything unless an item
        explicitly opts in via `overrides`."""
        master = _minimal_master()
        facts = FactsBank(extra_bullets=[FactItem(id="enrich-1", text="Something new")])
        idx = build_source_index(master, facts)
        assert "master:exp-1-b1" in idx
        assert "facts:enrich-1" in idx

    def test_override_on_project_field_also_shadows(self) -> None:
        """Overrides on `projects` entries work the same way as `extra_bullets`."""
        master = _minimal_master()
        facts = FactsBank(
            projects=[
                FactItem(id="proj-1", text="Rebuilt the auth layer", overrides="master:exp-1-b1")
            ]
        )
        idx = build_source_index(master, facts)
        assert "master:exp-1-b1" not in idx
        assert "facts:proj-1" in idx

    def test_override_targeting_missing_master_id_is_ignored(self) -> None:
        """A stale override pointing at a deleted master entry doesn't break the
        index build — the override just has no effect and the fact remains."""
        master = _minimal_master()
        facts = FactsBank(
            extra_bullets=[
                FactItem(id="enrich-1", text="Orphaned polish", overrides="master:exp-99-b99")
            ]
        )
        idx = build_source_index(master, facts)
        # Master is unchanged; the fact is still in the index under its own id.
        assert "master:exp-1-b1" in idx
        assert "facts:enrich-1" in idx

    def test_override_hides_master_skill(self) -> None:
        master = _minimal_master(skills=["Python"])
        facts = FactsBank(
            extra_bullets=[
                FactItem(id="enrich-1", text="Python (8+ years)", overrides="master:skill:Python")
            ]
        )
        idx = build_source_index(master, facts)
        assert "master:skill:Python" not in idx
        assert "facts:enrich-1" in idx
