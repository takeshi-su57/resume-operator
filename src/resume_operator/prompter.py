"""Prompter protocol — the single seam between interactive flows and their UI.

The iterative approval loop (#78) and the enrichment interview are the only
pieces of the pipeline that block on user input. Keeping them behind this
protocol lets the same business logic run under two frontends:

- `prompters.rich_prompter.RichPrompter` — the CLI, renders via `rich.console`
- a future `WebSocketPrompter` — the Tauri desktop shell, ferries every call
  over a websocket message so the React frontend can render a dense,
  keyboard-driven workspace instead of a terminal prompt

The protocol is intentionally narrow: decision primitives (`confirm`,
`choose`, `text`), a handful of semantic render calls for the domain objects
(`render_proposal`, `render_question`, `render_polished`,
`render_iteration_header`), two generic rendering escape hatches (`notice`,
`panel`), and a `status` context manager for long-running LLM calls. Rich
markup (`[bold]...[/bold]`) is passed through as-is; non-CLI implementations
are expected to translate or strip it.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from resume_operator.state import Proposal
    from resume_operator.tools.enrich import PolishedFactLLMOutput, Question


@runtime_checkable
class Prompter(Protocol):
    """The single seam between interactive flows and their UI."""

    # --- user decisions ---
    def confirm(self, message: str, *, default: bool = False) -> bool:
        """Yes/no gate. Returns True on yes."""
        ...

    def choose(self, message: str, choices: list[str], *, default: str) -> str:
        """Single-key choice among `choices`. Returned value is lower-cased."""
        ...

    def text(self, message: str, *, default: str = "") -> str:
        """Free-text input. Returned value is stripped."""
        ...

    # --- domain-specific rendering ---
    def render_proposal(self, proposal: Proposal, *, index: int, total: int) -> None:
        """Show a single LLM proposal (rewrite_master / rewrite_fact / new_fact / new_skill)."""
        ...

    def render_iteration_header(self, *, iteration: int, max_iter: int, score: float) -> None:
        """Show the approval-loop iteration banner with the current ATS score."""
        ...

    def render_question(self, question: Question, *, index: int, total: int) -> None:
        """Show a single enrichment interview question."""
        ...

    def render_polished(self, polished: PolishedFactLLMOutput) -> None:
        """Show the LLM-polished version of a user answer during enrichment."""
        ...

    # --- generic rendering escape hatches ---
    def notice(self, message: str, *, style: str = "") -> None:
        """Short status message. `style` is a Rich colour tag (e.g. "yellow")."""
        ...

    def panel(self, message: str, *, title: str, style: str = "") -> None:
        """Multi-line boxed message (intro panels, summaries, errors)."""
        ...

    # --- long-running operations ---
    def status(self, message: str) -> AbstractContextManager[None]:
        """Wrap a blocking call with a spinner / busy indicator."""
        ...
