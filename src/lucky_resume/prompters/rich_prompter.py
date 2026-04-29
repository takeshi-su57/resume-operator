"""CLI implementation of the `Prompter` protocol — wraps Rich.

Produces terminal output byte-identical to the pre-refactor CLI so users see
no behavior change from the prompter-seam introduction.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.status import Status

if TYPE_CHECKING:
    from lucky_resume.state import Proposal
    from lucky_resume.tools.enrich import PolishedFactLLMOutput, Question


# Human-readable labels for every `Proposal.kind` the LLM can emit (#80).
# Lives here because the CLI is the only renderer that needs them today —
# other Prompter implementations (e.g. WebSocketPrompter) will own their
# own labelling and don't import this dict.
_KIND_LABEL = {
    "rewrite_master": "Rewrite of your existing master bullet",
    "rewrite_fact": "Polish of a facts-bank entry",
    "new_fact": "NEW bullet (LLM extrapolation — verify truth)",
    "new_skill": "NEW skill (verify you actually have this)",
}


def _score_color(score: float) -> str:
    if score >= 0.7:
        return "green"
    if score >= 0.4:
        return "yellow"
    return "red"


class RichPrompter:
    """Renders the interactive flows via `rich.console.Console`."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console if console is not None else Console()

    # --- user decisions ---
    def confirm(self, message: str, *, default: bool = False) -> bool:
        return Confirm.ask(message, default=default, console=self.console)

    def choose(self, message: str, choices: list[str], *, default: str) -> str:
        raw = Prompt.ask(message, choices=choices, default=default, console=self.console)
        return raw.lower()

    def text(self, message: str, *, default: str = "") -> str:
        raw = Prompt.ask(message, default=default, console=self.console)
        return raw.strip()

    # --- domain-specific rendering ---
    def render_proposal(self, proposal: Proposal, *, index: int, total: int) -> None:
        label = _KIND_LABEL.get(proposal.kind, proposal.kind)
        lines: list[str] = [
            f"[bold]{label}[/bold]",
            f"[dim]grounded in {proposal.grounding_source_id}[/dim]",
            "",
        ]
        if proposal.original_text:
            lines.append(f"[bold]Original:[/bold]  {proposal.original_text}")
        lines.append(f"[bold green]Proposed:[/bold green] {proposal.proposed_text}")
        if proposal.rationale:
            lines.append("")
            lines.append(f"[dim]Why: {proposal.rationale}[/dim]")
        self.console.print(
            Panel(
                "\n".join(lines),
                title=f"Proposal {index}/{total}",
                border_style="cyan",
            )
        )

    def render_iteration_header(self, *, iteration: int, max_iter: int, score: float) -> None:
        color = _score_color(score)
        self.console.print(
            f"\n[bold]Iteration {iteration}/{max_iter}:[/bold] "
            f"ATS score on tailored output = [{color}]{score:.0%}[/{color}]"
        )

    def render_question(self, question: Question, *, index: int, total: int) -> None:
        self.console.print(
            f"\n[bold cyan]Question {index}/{total}:[/bold cyan] {question.question}"
        )
        if question.why:
            self.console.print(f"[dim]why: {question.why}[/dim]")
        self.console.print(
            '[dim]Answer with facts and metrics (e.g. "I built 50+ endpoints serving '
            "2M requests/day\"). Do NOT type instructions like 'make it professional' "
            "— that's the LLM's job in the polish step.[/dim]"
        )

    def render_polished(self, polished: PolishedFactLLMOutput) -> None:
        target = f" → [magenta]{polished.bucket}[/magenta]" + (
            f" (role_id={polished.role_id})" if polished.role_id else ""
        )
        self.console.print(f"\n[bold green]Polished:[/bold green]{target}")
        self.console.print(f"  {polished.polished_text}")

    # --- generic rendering escape hatches ---
    def notice(self, message: str, *, style: str = "") -> None:
        if style:
            self.console.print(f"[{style}]{message}[/{style}]")
        else:
            self.console.print(message)

    def panel(self, message: str, *, title: str, style: str = "") -> None:
        self.console.print(Panel(message, title=title, border_style=style or "cyan"))

    # --- long-running operations ---
    def status(self, message: str) -> AbstractContextManager[None]:
        return _status_cm(message, self.console)


@contextmanager
def _status_cm(message: str, console: Console) -> Iterator[None]:
    # Rich's `Status.__enter__` returns itself, not None, so wrap it in a
    # plain context manager to line up with the Prompter protocol.
    with Status(message, console=console):
        yield
