"""Integration tests for the #78 iterative tailor approval loop.

These tests hit `_run_approval_loop` directly with mocked tailor graph +
LLM calls, so we can assert on the loop's control flow (accept / quit /
cap / empty-proposals / approved-then-reloop) without running the whole
LangGraph pipeline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resume_operator.main import _run_approval_loop
from resume_operator.state import (
    ATSScore,
    FactItem,
    FactsBank,
    Proposal,
    ResumeMaster,
    TailoredItem,
    TailoredResume,
)
from resume_operator.tools.facts_bank import save_facts


def _tailor_result(
    score: float, iteration_id: str = "", tailored_items: int = 2
) -> dict[str, object]:
    """Build a minimal dict that _run_approval_loop can treat as a tailor-graph result."""
    return {
        "ats_score": ATSScore(score=score, reasoning=f"iter {iteration_id}"),
        "tailored_resume": TailoredResume(
            items=[
                TailoredItem(source_id=f"master:exp-1-b{i}", action="keep")
                for i in range(tailored_items)
            ],
            tailored_summary=f"Tailored summary iter {iteration_id}",
        ),
        "master": ResumeMaster(name="Test"),
        "facts": FactsBank(),
        "job_description_path": "",
        "errors": [],
    }


@pytest.fixture
def facts_path(tmp_path: Path) -> Path:
    path = tmp_path / "facts.yaml"
    save_facts(FactsBank(), path)
    return path


class TestApprovalLoop:
    @patch("rich.prompt.Confirm.ask")
    def test_user_accepts_on_first_iteration(
        self, mock_confirm: MagicMock, facts_path: Path
    ) -> None:
        """User clicks Accept on iter 1 → loop returns the first tailor result
        without touching propose_changes / approval_flow / apply_approvals."""
        mock_confirm.return_value = True  # Accept the first tailored version
        tailor_graph = MagicMock()
        tailor_graph.invoke.side_effect = AssertionError(
            "tailor_graph should not be re-invoked when user accepts iter 1"
        )

        initial_result = _tailor_result(score=0.75, iteration_id="1")
        initial_input = {"facts_path": str(facts_path)}

        final = _run_approval_loop(
            tailor_graph=tailor_graph,
            initial_result=initial_result,
            initial_input=initial_input,
            max_iterations=3,
        )
        assert final is initial_result

    @patch("resume_operator.nodes.apply_approvals.apply_approvals")
    @patch("resume_operator.tools.approval_flow.run_approval_flow")
    @patch("resume_operator.nodes.propose_changes.propose_changes")
    @patch("rich.prompt.Confirm.ask")
    def test_reject_then_approve_triggers_reloop(
        self,
        mock_confirm: MagicMock,
        mock_propose: MagicMock,
        mock_approval: MagicMock,
        mock_apply: MagicMock,
        facts_path: Path,
    ) -> None:
        """iter 1: user rejects → propose → approve → apply → re-invoke tailor.
        iter 2: user accepts the improved version."""
        # User rejects iter 1, accepts iter 2. The loop asks Confirm once per iteration.
        mock_confirm.side_effect = [False, True]
        mock_propose.return_value = {
            "proposals": [
                Proposal(
                    kind="rewrite_master",
                    grounding_source_id="master:exp-1-b0",
                    proposed_text="Polished",
                )
            ]
        }
        mock_approval.return_value = MagicMock(
            approved=[
                Proposal(
                    kind="rewrite_master",
                    grounding_source_id="master:exp-1-b0",
                    proposed_text="Polished",
                )
            ],
            rejected=[],
            quit_early=False,
        )
        mock_apply.return_value = {}

        tailor_graph = MagicMock()
        # iter 2 tailor output (higher score after the approved fact lands).
        tailor_graph.invoke.return_value = _tailor_result(score=0.85, iteration_id="2")

        initial_result = _tailor_result(score=0.70, iteration_id="1")
        final = _run_approval_loop(
            tailor_graph=tailor_graph,
            initial_result=initial_result,
            initial_input={"facts_path": str(facts_path)},
            max_iterations=3,
        )

        # Iter 2's tailor output wins.
        ats = final.get("ats_score")
        assert isinstance(ats, ATSScore) and ats.score == pytest.approx(0.85)
        mock_propose.assert_called_once()
        mock_approval.assert_called_once()
        mock_apply.assert_called_once()
        tailor_graph.invoke.assert_called_once()

    @patch("resume_operator.nodes.propose_changes.propose_changes")
    @patch("rich.prompt.Confirm.ask")
    def test_empty_proposals_returns_best_seen(
        self,
        mock_confirm: MagicMock,
        mock_propose: MagicMock,
        facts_path: Path,
    ) -> None:
        """When the LLM has no proposals to make, the loop gives up and returns
        the best-scoring iteration seen so far."""
        mock_confirm.return_value = False  # User rejects iter 1
        mock_propose.return_value = {"proposals": []}

        tailor_graph = MagicMock()  # shouldn't be re-invoked
        initial_result = _tailor_result(score=0.60, iteration_id="1")

        final = _run_approval_loop(
            tailor_graph=tailor_graph,
            initial_result=initial_result,
            initial_input={"facts_path": str(facts_path)},
            max_iterations=3,
        )
        assert final is initial_result  # best is the initial, since it's the only one seen
        tailor_graph.invoke.assert_not_called()

    @patch("resume_operator.nodes.apply_approvals.apply_approvals")
    @patch("resume_operator.tools.approval_flow.run_approval_flow")
    @patch("resume_operator.nodes.propose_changes.propose_changes")
    @patch("rich.prompt.Confirm.ask")
    def test_quit_early_returns_best_seen(
        self,
        mock_confirm: MagicMock,
        mock_propose: MagicMock,
        mock_approval: MagicMock,
        mock_apply: MagicMock,
        facts_path: Path,
    ) -> None:
        """User hits [q] in approval UX → loop returns the best-scoring tailor
        result seen (which is the current one, since no re-run happened)."""
        mock_confirm.return_value = False
        mock_propose.return_value = {
            "proposals": [
                Proposal(
                    kind="new_fact",
                    grounding_source_id="master:exp-1-b0",
                    proposed_text="x",
                )
            ]
        }
        mock_approval.return_value = MagicMock(approved=[], rejected=[], quit_early=True)
        mock_apply.return_value = {}

        tailor_graph = MagicMock()
        initial_result = _tailor_result(score=0.55)
        final = _run_approval_loop(
            tailor_graph=tailor_graph,
            initial_result=initial_result,
            initial_input={"facts_path": str(facts_path)},
            max_iterations=3,
        )
        assert final is initial_result
        mock_apply.assert_not_called()  # quit_early means we don't persist anything

    @patch("resume_operator.nodes.apply_approvals.apply_approvals")
    @patch("resume_operator.tools.approval_flow.run_approval_flow")
    @patch("resume_operator.nodes.propose_changes.propose_changes")
    @patch("rich.prompt.Confirm.ask")
    def test_iteration_cap_with_decline_returns_best(
        self,
        mock_confirm: MagicMock,
        mock_propose: MagicMock,
        mock_approval: MagicMock,
        mock_apply: MagicMock,
        facts_path: Path,
    ) -> None:
        """After `max_iterations` consecutive No-accepts, the continue-anyway
        prompt fires. User declines → loop returns the best iteration seen."""
        # max_iter=1 means: iter 1 accept? No → cap hits → continue anyway? No → return best.
        # Each iteration asks ONE Confirm (accept?). When that's No on the final iteration,
        # the cap prompt fires (a SECOND Confirm).
        mock_confirm.side_effect = [False, False]  # accept? N, continue anyway? N
        mock_propose.return_value = {"proposals": []}  # doesn't matter

        tailor_graph = MagicMock()
        initial_result = _tailor_result(score=0.65, iteration_id="1")
        final = _run_approval_loop(
            tailor_graph=tailor_graph,
            initial_result=initial_result,
            initial_input={"facts_path": str(facts_path)},
            max_iterations=1,
        )
        assert final is initial_result
        # propose_changes was NOT called — the cap-decline path exits before
        # propose runs.
        mock_propose.assert_not_called()

    @patch("resume_operator.nodes.apply_approvals.apply_approvals")
    @patch("resume_operator.tools.approval_flow.run_approval_flow")
    @patch("resume_operator.nodes.propose_changes.propose_changes")
    @patch("rich.prompt.Confirm.ask")
    def test_best_so_far_preserved_across_iterations(
        self,
        mock_confirm: MagicMock,
        mock_propose: MagicMock,
        mock_approval: MagicMock,
        mock_apply: MagicMock,
        facts_path: Path,
    ) -> None:
        """Iter 1 scores 0.80; iter 2 regresses to 0.60; user quits. Loop
        should return iter 1 (best), not iter 2 (current)."""
        # accept iter 1? No. accept iter 2? No → propose, then quit_early.
        mock_confirm.side_effect = [False, False]
        mock_propose.return_value = {
            "proposals": [
                Proposal(
                    kind="new_fact",
                    grounding_source_id="master:exp-1-b0",
                    proposed_text="x",
                )
            ]
        }
        # First approve call (after iter 1): returns an approval, triggers iter 2.
        # Second approve call (after iter 2): quit_early.
        mock_approval.side_effect = [
            MagicMock(
                approved=[
                    Proposal(
                        kind="rewrite_master",
                        grounding_source_id="master:exp-1-b0",
                        proposed_text="Polished",
                    )
                ],
                rejected=[],
                quit_early=False,
            ),
            MagicMock(approved=[], rejected=[], quit_early=True),
        ]
        mock_apply.return_value = {}

        tailor_graph = MagicMock()
        tailor_graph.invoke.return_value = _tailor_result(score=0.60, iteration_id="2")

        initial_result = _tailor_result(score=0.80, iteration_id="1")

        final = _run_approval_loop(
            tailor_graph=tailor_graph,
            initial_result=initial_result,
            initial_input={"facts_path": str(facts_path)},
            max_iterations=3,
        )
        # Iter 1 was the best (0.80) — that's what the quit-early path returns.
        assert final is initial_result


class TestApprovalLoopIntegration:
    """Integration-ish tests that exercise more plumbing without mocking propose_changes."""

    def test_overrides_hide_master_in_source_index(self, tmp_path: Path) -> None:
        """Sanity: when apply_approvals writes a fact with an override, the
        next `build_source_index` call drops the shadowed master entry."""
        from resume_operator.state import ExperienceBullet, ExperienceEntry, ResumeMaster
        from resume_operator.tools.source_index import build_source_index

        master = ResumeMaster(
            name="x",
            experience=[
                ExperienceEntry(
                    id="exp-1",
                    role="Eng",
                    bullets=[ExperienceBullet(id="exp-1-b1", text="orig")],
                )
            ],
        )
        facts = FactsBank(
            extra_bullets=[FactItem(id="approved-1", text="polished", overrides="master:exp-1-b1")]
        )
        idx = build_source_index(master, facts)
        assert "master:exp-1-b1" not in idx
        assert "facts:approved-1" in idx
