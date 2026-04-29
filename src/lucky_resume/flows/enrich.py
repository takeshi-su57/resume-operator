"""Auto-enrichment orchestration — former `main._run_auto_enrich`.

Called after a tailoring pass that came back thin (kept+reworded items
below `enrich_threshold`). Offers an interactive interview, runs it
through the injected `Prompter`, and persists accepted items to the
facts bank on disk.

Returns True if any items landed in the facts bank, so the caller knows
to re-invoke the tailor graph with the enriched facts.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lucky_resume.state import FactsBank
from lucky_resume.tools.enrich import (
    assemble_additions,
    collect_existing_ids,
    run_interactive_session,
)
from lucky_resume.tools.facts_bank import append_to_facts, load_facts
from lucky_resume.tools.master_resume import load_master

if TYPE_CHECKING:
    from lucky_resume.prompter import Prompter


DEFAULT_FACTS_PATH = Path("data/facts_bank.yaml")


def run_auto_enrich(
    *,
    prompter: Prompter,
    master_path: Path,
    facts_path: Path | None,
    jd_text: str,
) -> bool:
    """Pause the pipeline, prompt for an enrichment session, persist accepted items.

    Returns True if any items were appended to the facts bank (so the caller
    knows to re-invoke the graph), False otherwise.
    """
    prompter.panel(
        "Only a few items landed in the tailored resume — your master + "
        "facts may be thin for this JD. We can grow your facts bank with "
        "a short interview now (LLM asks grounded questions, you answer "
        "in your own words, LLM polishes the phrasing).",
        title="Enrichment available",
        style="yellow",
    )
    if prompter.choose("Start an enrichment session?", choices=["y", "n"], default="y") != "y":
        return False

    target_facts = facts_path or DEFAULT_FACTS_PATH
    master_obj = load_master(master_path)
    facts_obj = load_facts(target_facts) if target_facts.exists() else FactsBank()

    plan = run_interactive_session(master_obj, facts_obj, jd_text, prompter=prompter)
    if not plan.items:
        prompter.notice("No items accepted — facts_bank unchanged.", style="yellow")
        return False

    existing_ids = collect_existing_ids(facts_obj)
    projects, extra_bullets, skills, certifications = assemble_additions(
        plan, existing_ids=existing_ids
    )
    append_to_facts(
        target_facts,
        projects=projects,
        extra_bullets=extra_bullets,
        skills=skills,
        certifications=certifications,
    )
    prompter.panel(
        f"[bold]Wrote:[/bold] {target_facts}\n"
        f"Projects: +{len(projects)}  |  Extra bullets: +{len(extra_bullets)}  |  "
        f"Skills: +{len(skills)}  |  Certs: +{len(certifications)}",
        title="Facts bank updated",
        style="green",
    )
    return True
