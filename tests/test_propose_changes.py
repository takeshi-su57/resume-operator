"""Tests for the `propose_changes` node + `revise_proposal` helper (#78)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from resume_operator.nodes.propose_changes import (
    MAX_PROPOSALS_PER_ITERATION,
    ProposalLLM,
    ProposeChangesLLMOutput,
    propose_changes,
    revise_proposal,
)
from resume_operator.state import (
    Proposal,
    RejectedSuggestion,
    ResumeOptimizerState,
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


class TestProposeChanges:
    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_emits_validated_proposals(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        # sample_state has master:exp-1-b1 "Led backend team" and master:exp-1-b2
        # "Built microservices in Python"; JD wants Kubernetes + CI/CD.
        mock_get_llm.return_value = _make_llm(
            ProposeChangesLLMOutput(
                proposals=[
                    ProposalLLM(
                        kind="rewrite_master",
                        grounding_source_id="master:exp-1-b1",
                        original_text="Led backend team",
                        proposed_text=(
                            "Led backend team building Kubernetes-orchestrated services"
                        ),
                        rationale="Surfaces the Kubernetes keyword from the JD",
                    ),
                    ProposalLLM(
                        kind="new_fact",
                        grounding_source_id="master:exp-1-b2",
                        proposed_text="Built CI/CD pipelines for microservice deploys",
                        rationale="Covers the CI/CD gap",
                        target_role_id="exp-1",
                    ),
                ],
                notes=["Targeting the JD's K8s + CI/CD gaps"],
            )
        )

        result = propose_changes(sample_state)

        proposals = result["proposals"]
        assert len(proposals) == 2
        assert proposals[0].kind == "rewrite_master"
        # For rewrite_* kinds, original_text is anchored to the canonical menu text,
        # not whatever the LLM echoed back.
        assert proposals[0].original_text == "Led backend team"
        assert "Kubernetes" in proposals[0].proposed_text
        # new_fact carries its target_role_id through.
        assert proposals[1].kind == "new_fact"
        assert proposals[1].target_role_id == "exp-1"

    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_rejects_fabricated_grounding_source_id(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            ProposeChangesLLMOutput(
                proposals=[
                    ProposalLLM(
                        kind="rewrite_master",
                        grounding_source_id="master:exp-99-b99",  # does not exist
                        proposed_text="Some polished bullet",
                    ),
                    ProposalLLM(
                        kind="rewrite_master",
                        grounding_source_id="master:exp-1-b1",  # exists
                        proposed_text="Led backend team building K8s services",
                    ),
                ]
            )
        )
        result = propose_changes(sample_state)
        assert len(result["proposals"]) == 1
        assert result["proposals"][0].grounding_source_id == "master:exp-1-b1"
        assert any(
            "fabricated grounding_source_id: master:exp-99-b99" in e for e in result["errors"]
        )

    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_trims_to_max_proposals(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        # Twice the cap — validate that the node trims.
        raw = [
            ProposalLLM(
                kind="rewrite_master",
                grounding_source_id="master:exp-1-b1",
                proposed_text=f"Polished variant {i}",
            )
            for i in range(MAX_PROPOSALS_PER_ITERATION * 2)
        ]
        mock_get_llm.return_value = _make_llm(ProposeChangesLLMOutput(proposals=raw))
        result = propose_changes(sample_state)
        assert len(result["proposals"]) == MAX_PROPOSALS_PER_ITERATION

    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_coerces_unknown_kind(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            ProposeChangesLLMOutput(
                proposals=[
                    ProposalLLM(
                        kind="invent",  # not in allowed set
                        grounding_source_id="master:exp-1-b1",
                        proposed_text="Rewritten",
                    )
                ]
            )
        )
        result = propose_changes(sample_state)
        # Falls back to the prefix-inferred kind — master:* → rewrite_master.
        assert result["proposals"][0].kind == "rewrite_master"

    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_skips_empty_proposed_text(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            ProposeChangesLLMOutput(
                proposals=[
                    ProposalLLM(
                        kind="rewrite_master",
                        grounding_source_id="master:exp-1-b1",
                        proposed_text="   ",  # whitespace-only
                    )
                ]
            )
        )
        result = propose_changes(sample_state)
        assert result["proposals"] == []

    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_rejection_list_flows_into_prompt(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        """The rejected_suggestions list must show up in the LLM prompt so it
        knows what NOT to re-propose."""
        sample_state.rejected_suggestions = [
            RejectedSuggestion(
                kind="new_fact",
                grounding_source_id="master:exp-1-b1",
                rejected_text="Led 50-cluster K8s migration",
                user_reason="I never used K8s, only ECS",
            )
        ]
        mock_llm = _make_llm(ProposeChangesLLMOutput(proposals=[]))
        mock_get_llm.return_value = mock_llm

        propose_changes(sample_state)

        sent_prompt: str = mock_llm.invoke.call_args.args[0]
        assert "I never used K8s, only ECS" in sent_prompt
        assert "master:exp-1-b1" in sent_prompt

    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API down"))
        result = propose_changes(sample_state)
        assert result["proposals"] == []
        assert any("LLM call failed" in e for e in result["errors"])

    def test_skips_when_master_is_empty(self) -> None:
        state = ResumeOptimizerState()
        result = propose_changes(state)
        assert result["proposals"] == []
        assert any("source index is empty" in e for e in result["errors"])


class TestReviseProposal:
    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_returns_revised_proposal(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            ProposalLLM(
                kind="rewrite_master",
                grounding_source_id="master:exp-1-b1",
                proposed_text="Led backend team building ECS-orchestrated services",
                rationale="Corrected K8s -> ECS per user feedback",
            )
        )
        original = Proposal(
            kind="rewrite_master",
            grounding_source_id="master:exp-1-b1",
            original_text="Led backend team",
            proposed_text="Led backend team building Kubernetes-orchestrated services",
            rationale="Surface K8s",
        )

        revised = revise_proposal(
            sample_state, original, user_feedback="I never used K8s, only ECS"
        )

        assert revised is not None
        assert "ECS" in revised.proposed_text
        assert "Kubernetes" not in revised.proposed_text

    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_returns_none_on_fabricated_revision(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            ProposalLLM(
                kind="rewrite_master",
                grounding_source_id="master:exp-99-b99",  # fabricated
                proposed_text="Something",
            )
        )
        original = Proposal(
            kind="rewrite_master",
            grounding_source_id="master:exp-1-b1",
            proposed_text="Prior",
        )
        assert revise_proposal(sample_state, original, "feedback") is None

    @patch("resume_operator.nodes.propose_changes.get_structured_llm")
    def test_returns_none_on_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("boom"))
        original = Proposal(
            kind="rewrite_master",
            grounding_source_id="master:exp-1-b1",
            proposed_text="Prior",
        )
        assert revise_proposal(sample_state, original, "feedback") is None
