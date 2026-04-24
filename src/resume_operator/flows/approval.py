"""Iterative tailor → score → gate → propose → approve → apply → re-tailor loop.

This is the body of the former `main._run_approval_loop`, refactored to
take a `Prompter` seam so it can be driven either from the CLI (via
`RichPrompter`) or the server (via `WebSocketPrompter`, Phase 1).

The loop exits when (a) the user accepts the current ATS score, (b) the
LLM produces no proposals, (c) the user quits mid-approval, or (d) the
user declines to continue past the iteration cap — in which case the
best-scoring iteration seen so far is returned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from resume_operator.state import ATSScore, RejectedSuggestion, ResumeOptimizerState

if TYPE_CHECKING:
    from resume_operator.prompter import Prompter


def result_score(result: dict[str, Any]) -> float:
    """Extract the composite ATS score from a tailor-graph result dict.

    The graph sometimes returns `ats_score` as a plain dict (pre-Pydantic
    hydration) and sometimes as a full `ATSScore` instance; this accepts
    both so callers don't need to care which stage of the pipeline they're
    reading from.
    """
    ats = result.get("ats_score")
    if isinstance(ats, ATSScore):
        return ats.score
    if isinstance(ats, dict):
        value = ats.get("score", 0.0)
        return float(value) if isinstance(value, (int, float)) else 0.0
    return 0.0


def run_approval_loop(
    *,
    prompter: Prompter,
    tailor_graph: Any,
    initial_result: dict[str, Any],
    initial_input: dict[str, Any],
    max_iterations: int,
) -> dict[str, Any]:
    """Drive the iterative tailor → score → gate → propose → approve → apply → re-tailor loop.

    Returns the final tailor-graph result the caller hands to the finalize
    step. `tailor_graph` is the compiled graph from
    `resume_operator.graph.build_tailor_graph` — duck-typed here so tests
    can pass a `MagicMock`.
    """
    from resume_operator.nodes.apply_approvals import apply_approvals
    from resume_operator.nodes.propose_changes import propose_changes, revise_proposal
    from resume_operator.tools.approval_flow import run_approval_flow

    current = initial_result
    best = current
    best_score = result_score(current)
    iteration = 1
    max_iter_current = max_iterations
    accumulated_rejections: list[RejectedSuggestion] = []

    while True:
        score = result_score(current)
        if score > best_score:
            best, best_score = current, score

        prompter.render_iteration_header(
            iteration=iteration, max_iter=max_iter_current, score=score
        )
        if prompter.confirm(
            "[bold]Accept this tailored version and generate the PDF?[/bold]",
            default=False,
        ):
            return current

        if iteration >= max_iter_current:
            prompter.notice(
                f"Reached {max_iter_current} iterations (best ATS={best_score:.0%}). "
                "Continue iterating?",
                style="yellow",
            )
            if not prompter.confirm("Continue anyway?", default=False):
                prompter.notice("Using the best-scoring tailored version so far.", style="cyan")
                return best
            # Reset counter — user opted in for more. Add another cap on top.
            max_iter_current = iteration + max_iterations

        # Build a state object for propose + approval + apply (these nodes are
        # called directly, not through the graph).
        state = ResumeOptimizerState.model_validate(current)
        state.rejected_suggestions = list(accumulated_rejections)

        with prompter.status("[bold cyan]LLM proposing tailored edits..."):
            proposal_out = propose_changes(state)
        proposals = proposal_out.get("proposals", [])
        if not proposals:
            prompter.notice(
                "LLM had no proposals this iteration — sticking with the best version so far.",
                style="yellow",
            )
            return best

        outcome = run_approval_flow(
            state,
            list(proposals),
            revise_fn=revise_proposal,
            prompter=prompter,
        )
        accumulated_rejections.extend(outcome.rejected)
        if outcome.quit_early:
            prompter.notice(
                "You quit the approval step — using the best tailored version so far.",
                style="cyan",
            )
            return best
        if not outcome.approved:
            # User rejected everything. No new facts — next tailor pass would
            # produce the same output. Exit with the best seen.
            prompter.notice(
                "Nothing approved this iteration — using the best version so far.",
                style="cyan",
            )
            return best

        state.approved_proposals = list(outcome.approved)
        apply_approvals(state)  # writes to facts_bank.yaml on disk

        with prompter.status("[bold cyan]Re-tailoring with the approved facts..."):
            current = tailor_graph.invoke(initial_input)
        iteration += 1
