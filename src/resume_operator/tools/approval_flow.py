"""Three-button + Fix-loop approval UX for #78.

The approval flow is stdin-driven: for each proposal, the user sees the
original/proposed pair and picks `[y]es`, `[n]o`, or `[f]ix`. `Yes` puts
the proposal into the approved bucket; `No` records a `RejectedSuggestion`
with the user's optional reason so the next iteration's
`propose_changes` pass knows what NOT to re-propose; `Fix` prompts for
free-text feedback, calls `revise_proposal` to produce v2, and comes
back to the same three-button gate on v2 — unbounded.

The flow is kept out of `main.py` so the graph can call it through a
single seam and tests can inject scripted console/stdin via
`console_input`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from resume_operator.state import Proposal, RejectedSuggestion, ResumeOptimizerState

if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)


# Function type for the LLM Fix-loop revision call. Declared as a protocol so
# tests can inject a scripted revision function without monkeypatching the
# propose_changes module.
ReviseFn = Callable[[ResumeOptimizerState, Proposal, str], "Proposal | None"]


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
    console: Console | None = None,
) -> ApprovalOutcome:
    """Walk the user through `proposals` one by one. Return an `ApprovalOutcome`
    the caller merges back into state.

    `revise_fn` is injected so tests and the real wiring can differ — production
    passes `propose_changes.revise_proposal`; tests pass a scripted function.
    """
    from rich.console import Console

    active_console = console if console is not None else Console()

    if not proposals:
        active_console.print("[dim]No proposals to review this iteration.[/dim]")
        return ApprovalOutcome()

    outcome = ApprovalOutcome()
    total = len(proposals)
    for i, original in enumerate(proposals, 1):
        current = original
        # Fix loop — each `Fix` replaces `current` with a revised proposal and loops
        # back to the Y/N/F gate. Unbounded by design.
        while True:
            _render_proposal(active_console, current, index=i, total=total)
            choice = _ask_choice(active_console)
            if choice == "q":
                outcome.quit_early = True
                return outcome
            if choice == "y":
                outcome.approved.append(current)
                break
            if choice == "n":
                reason = _ask_reason(active_console)
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
            feedback = _ask_feedback(active_console)
            if not feedback:
                active_console.print(
                    "[yellow]Empty feedback — keeping the current proposal on screen.[/yellow]"
                )
                continue
            revised = revise_fn(state, current, feedback)
            if revised is None:
                active_console.print(
                    "[red]Revision failed (LLM error or fabricated grounding). "
                    "Keeping the previous proposal.[/red]"
                )
                continue
            current = revised
            active_console.print("[green]Got a revised version — here it is.[/green]")

    return outcome


# --- presentation helpers -------------------------------------------------


_KIND_LABEL = {
    "rewrite_master": "Rewrite of your existing master bullet",
    "rewrite_fact": "Polish of a facts-bank entry",
    "new_fact": "NEW bullet (LLM extrapolation — verify truth)",
    "new_skill": "NEW skill (verify you actually have this)",
}


def _render_proposal(console: Console, p: Proposal, *, index: int, total: int) -> None:
    from rich.panel import Panel

    label = _KIND_LABEL.get(p.kind, p.kind)
    body_lines: list[str] = [
        f"[bold]{label}[/bold]",
        f"[dim]grounded in {p.grounding_source_id}[/dim]",
        "",
    ]
    if p.original_text:
        body_lines.append(f"[bold]Original:[/bold]  {p.original_text}")
    body_lines.append(f"[bold green]Proposed:[/bold green] {p.proposed_text}")
    if p.rationale:
        body_lines.append("")
        body_lines.append(f"[dim]Why: {p.rationale}[/dim]")
    console.print(
        Panel(
            "\n".join(body_lines),
            title=f"Proposal {index}/{total}",
            border_style="cyan",
        )
    )


def _ask_choice(console: Console) -> str:
    from rich.prompt import Prompt

    return Prompt.ask(
        "[Y]es / [N]o / [F]ix — give feedback, LLM revises / [q]uit",
        choices=["y", "n", "f", "q"],
        default="y",
        console=console,
    ).lower()


def _ask_reason(console: Console) -> str:
    from rich.prompt import Prompt

    raw = Prompt.ask(
        "[dim]Why not? (optional — helps the LLM avoid the same idea next iteration)[/dim]",
        default="",
        console=console,
    )
    return raw.strip()


def _ask_feedback(console: Console) -> str:
    from rich.prompt import Prompt

    raw = Prompt.ask(
        "[bold]What should change?[/bold] "
        '[dim](free text — e.g. "I never used K8s, only ECS")[/dim]',
        default="",
        console=console,
    )
    return raw.strip()
