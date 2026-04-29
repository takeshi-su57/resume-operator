"""Three-button + Fix-loop approval UX for #78.

The approval flow gates each LLM proposal with `[y]es / [n]o / [f]ix`.
`Yes` puts the proposal into the approved bucket; `No` records a
`RejectedSuggestion` with the user's optional reason so the next
iteration's `propose_changes` pass knows what NOT to re-propose; `Fix`
prompts for free-text feedback, calls `revise_proposal` to produce v2,
and comes back to the same three-button gate on v2 — unbounded.

All user interaction and rendering goes through a `Prompter` seam so the
same flow can drive the CLI (`RichPrompter`) or the desktop GUI
(`WebSocketPrompter`, Phase 1). This module owns the control flow and the
single source of truth for `_KIND_LABEL`; the renderer decides how to
actually display them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lucky_resume.state import Proposal, RejectedSuggestion, ResumeOptimizerState

if TYPE_CHECKING:
    from lucky_resume.prompter import Prompter

logger = logging.getLogger(__name__)


# Function type for the LLM Fix-loop revision call. Declared as a protocol so
# tests can inject a scripted revision function without monkeypatching the
# propose_changes module.
ReviseFn = Callable[[ResumeOptimizerState, Proposal, str], "Proposal | None"]


# Human-readable labels for every `Proposal.kind` the LLM can emit (#80).
# Single source of truth — re-exported to any `Prompter` that wants to render
# the kind field in its own widget.
_KIND_LABEL = {
    "rewrite_master": "Rewrite of your existing master bullet",
    "rewrite_fact": "Polish of a facts-bank entry",
    "new_fact": "NEW bullet (LLM extrapolation — verify truth)",
    "new_skill": "NEW skill (verify you actually have this)",
}


@dataclass
class ApprovalOutcome:
    """Result of one full approval session over a batch of proposals."""

    approved: list[Proposal] = field(default_factory=list)
    rejected: list[RejectedSuggestion] = field(default_factory=list)
    # True when the user chose `[q]uit` mid-session — caller decides whether to
    # exit the loop or just stop proposing on this iteration.
    quit_early: bool = False


def run_approval_flow(
    state: ResumeOptimizerState,
    proposals: list[Proposal],
    *,
    revise_fn: ReviseFn,
    prompter: Prompter,
) -> ApprovalOutcome:
    """Walk the user through `proposals` one by one. Return an `ApprovalOutcome`
    the caller merges back into state.

    `revise_fn` is injected so tests and the real wiring can differ — production
    passes `propose_changes.revise_proposal`; tests pass a scripted function.
    """
    if not proposals:
        prompter.notice("No proposals to review this iteration.", style="dim")
        return ApprovalOutcome()

    outcome = ApprovalOutcome()
    total = len(proposals)
    for i, original in enumerate(proposals, 1):
        current = original
        # Fix loop — each `Fix` replaces `current` with a revised proposal and loops
        # back to the Y/N/F gate. Unbounded by design.
        while True:
            prompter.render_proposal(current, index=i, total=total)
            choice = prompter.choose(
                "[Y]es / [N]o / [F]ix — give feedback, LLM revises / [q]uit",
                choices=["y", "n", "f", "q"],
                default="y",
            )
            if choice == "q":
                outcome.quit_early = True
                return outcome
            if choice == "y":
                outcome.approved.append(current)
                break
            if choice == "n":
                reason = prompter.text(
                    "[dim]Why not? (optional — helps the LLM avoid the same idea "
                    "next iteration)[/dim]",
                    default="",
                )
                outcome.rejected.append(
                    RejectedSuggestion(
                        kind=current.kind,
                        grounding_source_id=current.grounding_source_id,
                        rejected_text=current.proposed_text,
                        user_reason=reason,
                    )
                )
                break
            # choice == "f" — Fix loop.
            feedback = prompter.text(
                "[bold]What should change?[/bold] "
                '[dim](free text — e.g. "I never used K8s, only ECS")[/dim]',
                default="",
            )
            if not feedback:
                prompter.notice(
                    "Empty feedback — keeping the current proposal on screen.",
                    style="yellow",
                )
                continue
            revised = revise_fn(state, current, feedback)
            if revised is None:
                prompter.notice(
                    "Revision failed (LLM error or fabricated grounding). "
                    "Keeping the previous proposal.",
                    style="red",
                )
                continue
            current = revised
            prompter.notice("Got a revised version — here it is.", style="green")

    return outcome
