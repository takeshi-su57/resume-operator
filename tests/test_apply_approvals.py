"""Tests for the `apply_approvals` node (#78).

The node drains `state.approved_proposals` into `facts_bank.yaml`. Tests use
`tmp_path` for the bank and assert on the round-tripped file so we exercise
the real YAML writer (not mocks).
"""

from __future__ import annotations

from pathlib import Path

from resume_operator.nodes.apply_approvals import apply_approvals
from resume_operator.state import (
    FactItem,
    FactsBank,
    Proposal,
    ResumeOptimizerState,
)
from resume_operator.tools.facts_bank import load_facts, save_facts


def _state_with_facts(
    path: Path, facts: FactsBank, proposals: list[Proposal]
) -> ResumeOptimizerState:
    save_facts(facts, path)
    return ResumeOptimizerState(
        facts_path=str(path),
        facts=facts,
        approved_proposals=proposals,
    )


class TestApplyApprovalsErrors:
    def test_empty_approvals_is_noop(self, tmp_path: Path) -> None:
        path = tmp_path / "facts.yaml"
        state = _state_with_facts(path, FactsBank(), [])
        result = apply_approvals(state)
        assert result == {"approved_proposals": []}
        # The file was never touched.
        assert not path.exists() or load_facts(path).projects == []

    def test_missing_facts_path_records_error(self) -> None:
        state = ResumeOptimizerState(
            facts_path="",
            approved_proposals=[
                Proposal(
                    kind="new_fact",
                    grounding_source_id="master:exp-1-b1",
                    proposed_text="Something",
                )
            ],
        )
        result = apply_approvals(state)
        assert any("no facts_path configured" in e for e in result["errors"])


class TestRewriteMaster:
    def test_appends_extra_bullet_with_overrides(self, tmp_path: Path) -> None:
        """A `rewrite_master` proposal grounded at a master bullet lands in
        extra_bullets with `overrides` set to the grounded source_id."""
        path = tmp_path / "facts.yaml"
        proposals = [
            Proposal(
                kind="rewrite_master",
                grounding_source_id="master:exp-2-b1",
                original_text="Led backend team",
                proposed_text="Led backend team building K8s-orchestrated services",
            )
        ]
        state = _state_with_facts(path, FactsBank(), proposals)

        result = apply_approvals(state)

        bank = load_facts(path)
        assert len(bank.extra_bullets) == 1
        fi = bank.extra_bullets[0]
        assert fi.text == "Led backend team building K8s-orchestrated services"
        assert fi.overrides == "master:exp-2-b1"
        # role_id inferred from the grounding.
        assert fi.role_id == "exp-2"
        # In-memory facts on the returned state reflect the disk write.
        assert result["facts"].extra_bullets[0].overrides == "master:exp-2-b1"

    def test_non_experience_grounding_lands_in_projects(self, tmp_path: Path) -> None:
        """rewrite_master on a non-experience source (e.g. master:edu-1) has no
        natural role_id so it lands in `projects`."""
        path = tmp_path / "facts.yaml"
        state = _state_with_facts(
            path,
            FactsBank(),
            [
                Proposal(
                    kind="rewrite_master",
                    grounding_source_id="master:edu-1",
                    proposed_text="BS CS, polished",
                )
            ],
        )
        apply_approvals(state)

        bank = load_facts(path)
        assert bank.extra_bullets == []
        assert len(bank.projects) == 1
        assert bank.projects[0].overrides == "master:edu-1"
        assert bank.projects[0].role_id == ""


class TestRewriteFact:
    def test_replaces_existing_fact_text(self, tmp_path: Path) -> None:
        path = tmp_path / "facts.yaml"
        starting_bank = FactsBank(
            extra_bullets=[
                FactItem(id="enrich-1", text="Old wording", role_id="exp-1", source="enrich")
            ]
        )
        proposals = [
            Proposal(
                kind="rewrite_fact",
                grounding_source_id="facts:enrich-1",
                original_text="Old wording",
                proposed_text="Polished wording matching the JD",
            )
        ]
        state = _state_with_facts(path, starting_bank, proposals)

        apply_approvals(state)

        bank = load_facts(path)
        # The same id is kept — source_index identity is stable.
        assert len(bank.extra_bullets) == 1
        assert bank.extra_bullets[0].id == "enrich-1"
        assert bank.extra_bullets[0].text == "Polished wording matching the JD"
        # role_id is preserved from the original.
        assert bank.extra_bullets[0].role_id == "exp-1"

    def test_missing_fact_id_is_skipped(self, tmp_path: Path) -> None:
        """If the user deleted the grounded fact between runs, the rewrite is
        silently skipped — no new fact created, no error."""
        path = tmp_path / "facts.yaml"
        state = _state_with_facts(
            path,
            FactsBank(),  # empty — nothing to rewrite
            [
                Proposal(
                    kind="rewrite_fact",
                    grounding_source_id="facts:gone",
                    proposed_text="Anything",
                )
            ],
        )
        apply_approvals(state)
        bank = load_facts(path)
        # The rewrite was a no-op; no new fact created.
        assert bank.projects == []
        assert bank.extra_bullets == []


class TestNewFact:
    def test_target_role_id_goes_to_extra_bullets(self, tmp_path: Path) -> None:
        path = tmp_path / "facts.yaml"
        state = _state_with_facts(
            path,
            FactsBank(),
            [
                Proposal(
                    kind="new_fact",
                    grounding_source_id="master:exp-1-b1",
                    proposed_text="Built CI/CD pipelines on GitHub Actions",
                    target_role_id="exp-1",
                )
            ],
        )
        apply_approvals(state)

        bank = load_facts(path)
        assert len(bank.extra_bullets) == 1
        assert bank.extra_bullets[0].role_id == "exp-1"
        # new_fact does NOT carry overrides — it's a net addition.
        assert bank.extra_bullets[0].overrides == ""

    def test_no_target_role_id_goes_to_projects(self, tmp_path: Path) -> None:
        path = tmp_path / "facts.yaml"
        state = _state_with_facts(
            path,
            FactsBank(),
            [
                Proposal(
                    kind="new_fact",
                    grounding_source_id="master:exp-1",
                    proposed_text="Standalone project extrapolated from experience",
                )
            ],
        )
        apply_approvals(state)

        bank = load_facts(path)
        assert len(bank.projects) == 1
        assert bank.projects[0].overrides == ""


class TestIdMinting:
    def test_minted_ids_are_unique_across_additions(self, tmp_path: Path) -> None:
        path = tmp_path / "facts.yaml"
        # Pre-existing fact taking up one id in the approved-YYYYMMDD-* space.
        import datetime

        prefix = f"approved-{datetime.date.today().strftime('%Y%m%d')}"
        starting_bank = FactsBank(projects=[FactItem(id=f"{prefix}-1", text="Existing")])
        proposals = [
            Proposal(
                kind="new_fact",
                grounding_source_id="master:exp-1-b1",
                proposed_text=f"New item {i}",
                target_role_id="exp-1",
            )
            for i in range(3)
        ]
        state = _state_with_facts(path, starting_bank, proposals)

        apply_approvals(state)

        bank = load_facts(path)
        all_ids = {fi.id for fi in (*bank.projects, *bank.extra_bullets)}
        # 1 pre-existing + 3 new = 4 unique ids, all distinct.
        assert len(all_ids) == 4
        # The new ids skip the collided -1 suffix.
        new_ids = {fi.id for fi in bank.extra_bullets}
        assert f"{prefix}-1" not in new_ids
