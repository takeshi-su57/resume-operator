"""Interactive post-bootstrap interview (#70).

After the LLM parses the PDF into a `ResumeMaster`, many of the senior-format
fields (headline, links, per-role tech, skill_groups) end up empty because the
source resume didn't carry them explicitly. Instead of silently leaving them
empty and telling the user to hand-edit the YAML, ask — one targeted prompt
per missing field, `skip` as the default, LLM-proposed skill grouping with
accept/reject UX.

User interaction goes through the injected `Prompter` seam so the same
logic serves both the CLI (`RichPrompter`) and the desktop GUI
(`WebSocketPrompter`). The CLI's `--no-interview` gating lives in
`should_run_interview`; the server's gating is explicit in the route
handler (it always runs when the WS session opens).
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from resume_operator.state import Link, ResumeMaster, SkillGroup
from resume_operator.tools.skill_grouping import propose_groups

if TYPE_CHECKING:
    from resume_operator.prompter import Prompter

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


def run_interview(master: ResumeMaster, *, prompter: Prompter) -> ResumeMaster:
    """Walk the user through the missing senior-format fields and fill them in.

    Returns the (possibly mutated) master. Safe to call with `no-interview`
    already filtered out upstream via `should_run_interview`.
    """
    prompter.panel(
        "Bootstrap parsed your PDF. A few fields couldn't be extracted "
        "because the source doesn't show them explicitly. Answer the prompts "
        "below (or hit Enter to skip each) and I'll stitch them into "
        "your master_resume.yaml.",
        title="Bootstrap interview",
        style="cyan",
    )

    _ask_headline(master, prompter)
    _ask_links(master, prompter)
    _ask_per_role_tech(master, prompter)
    _ask_skill_groups(master, prompter)

    return master


def _ask_headline(master: ResumeMaster, prompter: Prompter) -> None:
    if master.headline:
        return
    prompter.notice("\n[bold cyan]Headline[/bold cyan] — a 10-15 word tagline under your name.")
    prompter.notice(
        '[dim]Example: "Senior Backend Engineer · 10+ years · Node.js, AWS". '
        "This is a fallback — the tailor also writes a JD-specific headline per "
        "run. Type 'skip' to leave empty.[/dim]"
    )
    answer = prompter.text("[bold]>[/bold]", default="skip")
    if answer and answer.lower() != "skip":
        master.headline = answer


def _ask_links(master: ResumeMaster, prompter: Prompter) -> None:
    existing_labels = {lk.label.lower() for lk in master.links}
    missing = [label for label in _STANDARD_LINK_LABELS if label.lower() not in existing_labels]
    if not missing:
        return
    prompter.notice(
        "\n[bold cyan]Header links[/bold cyan] — Portfolio / LinkedIn / GitHub "
        "render as a second contact line."
    )
    prompter.notice("[dim]Type the URL or hit Enter (default 'skip') to skip each.[/dim]")
    for label in missing:
        answer = prompter.text(f"[bold]{label} URL[/bold]", default="skip")
        if answer and answer.lower() != "skip":
            master.links.append(Link(label=label, url=answer))


def _ask_per_role_tech(master: ResumeMaster, prompter: Prompter) -> None:
    roles_without_tech = [e for e in master.experience if not e.tech]
    if not roles_without_tech:
        return
    prompter.notice(
        f"\n[bold cyan]Per-role tech stacks[/bold cyan] — "
        f"{len(roles_without_tech)} role(s) need one."
    )
    prompter.notice(
        "[dim]For each role, type the tech comma-separated (e.g. "
        '"Python, PostgreSQL, AWS"). Hit Enter to skip.[/dim]'
    )
    for entry in roles_without_tech:
        label = f"{entry.role} @ {entry.company}".strip(" @") or entry.id
        answer = prompter.text(f"[bold]{label}[/bold]", default="skip")
        if not answer or answer.lower() == "skip":
            continue
        entry.tech = [t.strip() for t in answer.split(",") if t.strip()]


def _ask_skill_groups(master: ResumeMaster, prompter: Prompter) -> None:
    if master.skill_groups:
        return
    if len(master.skills) < _SKILL_GROUPING_MIN:
        return
    prompter.notice(
        f"\n[bold cyan]Skill grouping[/bold cyan] — you have {len(master.skills)} flat skills."
    )
    if not prompter.confirm(
        "Have the LLM propose categories (Languages / Frontend / Backend / Cloud / ...)?",
        default=True,
    ):
        return

    groups = propose_groups(master.skills)
    if not groups:
        prompter.notice(
            "LLM didn't return a usable grouping — leaving skills flat.",
            style="yellow",
        )
        return

    _print_groups(groups, prompter)
    choice = prompter.choose("[a]ccept / [r]eject", choices=["a", "r"], default="a")
    if choice == "a":
        master.skill_groups = groups


def _print_groups(groups: list[SkillGroup], prompter: Prompter) -> None:
    body = "\n".join(f"[bold]{g.category}[/bold]: {', '.join(g.items)}" for g in groups)
    prompter.panel(body, title="Proposed grouping", style="green")
