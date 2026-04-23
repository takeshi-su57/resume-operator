"""Tests for the three-button + Fix-loop approval UX (#78).

The flow is driven by `rich.prompt.Prompt.ask`, so tests script the user's
keystrokes by patching `Prompt.ask` with a `side_effect=iterator`. The LLM
revision call is injected via the `revise_fn` parameter so no mocking of
`propose_changes` is needed.
"""

from __future__ import annotations

from unittest.mock import patch

from rich.console import Console

from resume_operator.state import Proposal, ResumeOptimizerState
from resume_operator.tools.approval_flow import run_approval_flow


def _silent_console() -> Console:
    # record=True + no file makes the console silent enough for test output.
    return Console(file=None, quiet=True)


def _proposal(
    source_id: str = "master:exp-1-b1",
    kind: str = "rewrite_master",
    original: str = "Led backend team",
    proposed: str = "Led backend team building Kubernetes-orchestrated services",
) -> Proposal:
    return Proposal(
        kind=kind,
        grounding_source_id=source_id,
        original_text=original,
        proposed_text=proposed,
        rationale="Surface Kubernetes per the JD",
    )


def _scripted(answers: list[str]):  # noqa: ANN202 — just a helper
    """Return a side_effect callable that yields `answers` in order."""
    it = iter(answers)
    return lambda *a, **kw: next(it)


class TestRunApprovalFlow:
    def test_empty_proposals_returns_empty_outcome(self) -> None:
        state = ResumeOptimizerState()
        outcome = run_approval_flow(
            state, [], revise_fn=lambda *a, **kw: None, console=_silent_console()
        )
        assert outcome.approved == []
        assert outcome.rejected == []
        assert outcome.quit_early is False

    def test_yes_moves_to_approved(self) -> None:
        state = ResumeOptimizerState()
        p = _proposal()
        with patch("rich.prompt.Prompt.ask", side_effect=_scripted(["y"])):
            outcome = run_approval_flow(
                state, [p], revise_fn=lambda *a, **kw: None, console=_silent_console()
            )
        assert outcome.approved == [p]
        assert outcome.rejected == []

    def test_no_records_rejection_with_reason(self) -> None:
        state = ResumeOptimizerState()
        p = _proposal()
        # Scripted: choice="n", then reason="I never used K8s".
        with patch("rich.prompt.Prompt.ask", side_effect=_scripted(["n", "I never used K8s"])):
            outcome = run_approval_flow(
                state, [p], revise_fn=lambda *a, **kw: None, console=_silent_console()
            )
        assert outcome.approved == []
        assert len(outcome.rejected) == 1
        assert outcome.rejected[0].user_reason == "I never used K8s"
        assert outcome.rejected[0].rejected_text == p.proposed_text
        assert outcome.rejected[0].grounding_source_id == p.grounding_source_id

    def test_no_with_empty_reason_still_records_rejection(self) -> None:
        state = ResumeOptimizerState()
        p = _proposal()
        with patch("rich.prompt.Prompt.ask", side_effect=_scripted(["n", ""])):
            outcome = run_approval_flow(
                state, [p], revise_fn=lambda *a, **kw: None, console=_silent_console()
            )
        assert len(outcome.rejected) == 1
        assert outcome.rejected[0].user_reason == ""

    def test_fix_revises_and_re_gates_on_v2(self) -> None:
        """Fix → LLM emits v2 → user approves v2. Outcome holds v2, not v1."""
        state = ResumeOptimizerState()
        v1 = _proposal(proposed="Led K8s migration of 200 services")
        v2 = Proposal(
            kind=v1.kind,
            grounding_source_id=v1.grounding_source_id,
            original_text=v1.original_text,
            proposed_text="Led ECS migration of 200 services",
            rationale="Corrected K8s -> ECS per feedback",
        )

        def scripted_revise(
            _state: ResumeOptimizerState, _original: Proposal, feedback: str
        ) -> Proposal | None:
            assert "ECS" in feedback
            return v2

        # Scripted Prompt.ask: choice="f", feedback text, then choice="y" on v2.
        with patch(
            "rich.prompt.Prompt.ask",
            side_effect=_scripted(["f", "I never used K8s, only ECS", "y"]),
        ):
            outcome = run_approval_flow(
                state,
                [v1],
                revise_fn=scripted_revise,
                console=_silent_console(),
            )

        assert outcome.approved == [v2]
        # v1 is NOT in the rejected bucket — the Fix path replaced it, it wasn't
        # a rejection.
        assert outcome.rejected == []

    def test_fix_loop_unbounded_multiple_revisions(self) -> None:
        """User can click Fix repeatedly. Each Fix re-invokes revise_fn."""
        state = ResumeOptimizerState()
        v1 = _proposal()
        v2 = _proposal(proposed="v2 text")
        v3 = _proposal(proposed="v3 text")
        revisions = iter([v2, v3])

        def scripted_revise(*_args: object, **_kw: object) -> Proposal | None:
            return next(revisions)

        # f → feedback → f → feedback → y (accept v3)
        with patch(
            "rich.prompt.Prompt.ask",
            side_effect=_scripted(["f", "first feedback", "f", "second feedback", "y"]),
        ):
            outcome = run_approval_flow(
                state, [v1], revise_fn=scripted_revise, console=_silent_console()
            )
        assert outcome.approved == [v3]

    def test_fix_empty_feedback_keeps_current_proposal(self) -> None:
        """Empty feedback text after `f` doesn't call revise_fn; user is re-gated
        on the same proposal."""
        state = ResumeOptimizerState()
        p = _proposal()

        def should_not_be_called(*a: object, **kw: object) -> Proposal | None:
            raise AssertionError("revise_fn must not be invoked on empty feedback")

        # f → empty feedback → y (accept original, no revision happened)
        with patch("rich.prompt.Prompt.ask", side_effect=_scripted(["f", "", "y"])):
            outcome = run_approval_flow(
                state, [p], revise_fn=should_not_be_called, console=_silent_console()
            )
        assert outcome.approved == [p]

    def test_fix_llm_failure_keeps_current_proposal(self) -> None:
        """When revise_fn returns None (LLM error), the flow re-gates on the
        previous proposal — the user isn't punished for a transient failure."""
        state = ResumeOptimizerState()
        p = _proposal()

        # f → feedback → None from revise_fn → y on original
        with patch("rich.prompt.Prompt.ask", side_effect=_scripted(["f", "feedback", "y"])):
            outcome = run_approval_flow(
                state, [p], revise_fn=lambda *a, **kw: None, console=_silent_console()
            )
        assert outcome.approved == [p]

    def test_quit_short_circuits_remaining_proposals(self) -> None:
        state = ResumeOptimizerState()
        p1 = _proposal(source_id="master:exp-1-b1")
        p2 = _proposal(source_id="master:exp-1-b2")
        with patch("rich.prompt.Prompt.ask", side_effect=_scripted(["q"])):
            outcome = run_approval_flow(
                state,
                [p1, p2],
                revise_fn=lambda *a, **kw: None,
                console=_silent_console(),
            )
        assert outcome.quit_early is True
        assert outcome.approved == []
        # Rejected is also empty — quit means "stop, don't treat remaining as No".
        assert outcome.rejected == []
