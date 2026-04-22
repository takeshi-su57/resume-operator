"""Interactive post-bootstrap interview (#70).

After the LLM parses the PDF into a `ResumeMaster`, many of the senior-format
fields (headline, links, per-role tech, skill_groups) end up empty because the
source resume didn't carry them explicitly. Instead of silently leaving them
empty and telling the user to hand-edit the YAML, ask — one targeted prompt
per missing field, `skip` as the default, LLM-proposed skill grouping with
accept/reject UX.

The interview runs only when stdin is a TTY and the user hasn't opted out via
`--no-interview`. Headless/scripted runs pass through unchanged.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

from resume_operator.state import Link, ResumeMaster, SkillGroup
from resume_operator.tools.skill_grouping import propose_groups

if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)

# Standard link labels we always offer at interview time. The user's own master
# can carry any labels; these are just the common ones we prompt for by default.
_STANDARD_LINK_LABELS = ("Portfolio", "LinkedIn", "GitHub")

# Skip the skill-grouping prompt for tiny skill lists (not worth the LLM call
# or the user's attention).
_SKILL_GROUPING_MIN = 3


def should_run_interview(*, no_interview: bool) -> bool:
    """True when the interview should actually prompt the user.

    False when the user opted out explicitly, or when stdin is piped (CI,
    `echo ... | bootstrap`, etc.) — we never block on prompts in those cases.
    """
    if no_interview:
        return False
    return sys.stdin.isatty()


def run_interview(master: ResumeMaster, console: Console | None = None) -> ResumeMaster:
    """Walk the user through the missing senior-format fields and fill them in.

    Returns the (possibly mutated) master. Safe to call with `no-interview`
    already filtered out upstream via `should_run_interview`.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt

    active = console if console is not None else Console()
    active.print(
        Panel(
            "Bootstrap parsed your PDF. A few fields couldn't be extracted "
            "because the source doesn't show them explicitly. Answer the prompts "
            "below (or hit Enter to skip each) and I'll stitch them into "
            "your master_resume.yaml.",
            title="Bootstrap interview",
            border_style="cyan",
        )
    )

    _ask_headline(master, active, Prompt)
    _ask_links(master, active, Prompt)
    _ask_per_role_tech(master, active, Prompt)
    _ask_skill_groups(master, active, Prompt, Confirm)

    return master


def _ask_headline(master: ResumeMaster, console: Console, Prompt: Any) -> None:  # noqa: N803
    if master.headline:
        return
    console.print("\n[bold cyan]Headline[/bold cyan] — a 10-15 word tagline under your name.")
    console.print(
        '[dim]Example: "Senior Backend Engineer · 10+ years · Node.js, AWS". '
        "This is a fallback — the tailor also writes a JD-specific headline per "
        "run. Type 'skip' to leave empty.[/dim]"
    )
    answer = Prompt.ask("[bold]>[/bold]", default="skip", console=console)
    cleaned = answer.strip()
    if cleaned and cleaned.lower() != "skip":
        master.headline = cleaned


def _ask_links(master: ResumeMaster, console: Console, Prompt: Any) -> None:  # noqa: N803
    existing_labels = {lk.label.lower() for lk in master.links}
    missing = [label for label in _STANDARD_LINK_LABELS if label.lower() not in existing_labels]
    if not missing:
        return
    console.print(
        "\n[bold cyan]Header links[/bold cyan] — Portfolio / LinkedIn / GitHub "
        "render as a second contact line."
    )
    console.print("[dim]Type the URL or hit Enter (default 'skip') to skip each.[/dim]")
    for label in missing:
        answer = Prompt.ask(f"[bold]{label} URL[/bold]", default="skip", console=console)
        cleaned = answer.strip()
        if cleaned and cleaned.lower() != "skip":
            master.links.append(Link(label=label, url=cleaned))


def _ask_per_role_tech(master: ResumeMaster, console: Console, Prompt: Any) -> None:  # noqa: N803
    roles_without_tech = [e for e in master.experience if not e.tech]
    if not roles_without_tech:
        return
    console.print(
        f"\n[bold cyan]Per-role tech stacks[/bold cyan] — "
        f"{len(roles_without_tech)} role(s) need one."
    )
    console.print(
        "[dim]For each role, type the tech comma-separated (e.g. "
        '"Python, PostgreSQL, AWS"). Hit Enter to skip.[/dim]'
    )
    for entry in roles_without_tech:
        label = f"{entry.role} @ {entry.company}".strip(" @") or entry.id
        answer = Prompt.ask(f"[bold]{label}[/bold]", default="skip", console=console)
        cleaned = answer.strip()
        if not cleaned or cleaned.lower() == "skip":
            continue
        entry.tech = [t.strip() for t in cleaned.split(",") if t.strip()]


def _ask_skill_groups(
    master: ResumeMaster,
    console: Console,
    Prompt: Any,  # noqa: N803
    Confirm: Any,  # noqa: N803
) -> None:
    if master.skill_groups:
        return
    if len(master.skills) < _SKILL_GROUPING_MIN:
        return
    console.print(
        f"\n[bold cyan]Skill grouping[/bold cyan] — you have {len(master.skills)} flat skills."
    )
    if not Confirm.ask(
        "Have the LLM propose categories (Languages / Frontend / Backend / Cloud / ...)?",
        default=True,
        console=console,
    ):
        return

    groups = propose_groups(master.skills)
    if not groups:
        console.print("[yellow]LLM didn't return a usable grouping — leaving skills flat.[/yellow]")
        return

    _print_groups(groups, console)
    choice = Prompt.ask(
        "[a]ccept / [r]eject",
        choices=["a", "r"],
        default="a",
        console=console,
    )
    if choice == "a":
        master.skill_groups = groups


def _print_groups(groups: list[SkillGroup], console: Console) -> None:
    from rich.panel import Panel

    body = "\n".join(f"[bold]{g.category}[/bold]: {', '.join(g.items)}" for g in groups)
    console.print(Panel(body, title="Proposed grouping", border_style="green"))
