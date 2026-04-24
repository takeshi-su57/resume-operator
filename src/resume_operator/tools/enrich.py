"""Interactive enrichment session — LLM asks, user answers, LLM polishes.

Flow:
  1. `generate_questions(master, facts, jd)` → up to N `Question` objects.
  2. For each question, the session prompts the user for a free-text answer.
  3. `polish_answer(question, answer, master, jd)` → a `PolishedFact` that
     rewrites the answer as an ATS-ready bullet and classifies which
     facts_bank bucket it belongs in.
  4. The session shows the polished bullet and asks accept / edit / reject.
  5. `assemble_additions(accepted)` → four lists ready to hand to
     `tools.facts_bank.append_to_facts`.

The LLM-facing helpers (`generate_questions`, `polish_answer`,
`assemble_additions`, `collect_existing_ids`) are pure and testable without
stdin mocking. `run_interactive_session` drives the user-facing loop
through a `Prompter` seam so the same logic serves both the CLI and the
desktop GUI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.enrich import ENRICH_POLISH, ENRICH_QUESTIONS
from resume_operator.state import FactItem, FactsBank, ResumeMaster
from resume_operator.tools.llm_provider import get_structured_llm

if TYPE_CHECKING:
    from resume_operator.prompter import Prompter

logger = logging.getLogger(__name__)


# --- LLM output schemas ---------------------------------------------------


class EnrichQuestionLLM(BaseModel):
    area: str = ""
    question: str
    why: str = ""


class EnrichQuestionsLLMOutput(BaseModel):
    questions: list[EnrichQuestionLLM] = Field(default_factory=list)


class PolishedFactLLMOutput(BaseModel):
    """Polished resume bullet + bucket classification."""

    polished_text: str
    bucket: Literal["project", "extra_bullet", "skill", "certification"] = "project"
    role_id: str = ""  # only meaningful when bucket == "extra_bullet"


# --- Session-facing dataclasses ------------------------------------------


@dataclass
class Question:
    """A single interview question surfaced by the LLM."""

    area: str
    question: str
    why: str


@dataclass
class AcceptedItem:
    """One confirmed enrichment outcome ready to be written to facts_bank."""

    text: str
    bucket: Literal["project", "extra_bullet", "skill", "certification"]
    role_id: str = ""


@dataclass
class SessionPlan:
    """Bundle of accepted items from a single enrich session — what gets
    persisted. `assemble_additions` turns this into the four lists that
    `facts_bank.append_to_facts` expects."""

    items: list[AcceptedItem] = field(default_factory=list)


# --- LLM calls ------------------------------------------------------------


def generate_questions(
    master: ResumeMaster,
    facts: FactsBank,
    jd_text: str,
    *,
    n_max: int = 5,
) -> list[Question]:
    """Ask the LLM for up to `n_max` grounded interview questions."""
    llm = get_structured_llm(EnrichQuestionsLLMOutput)
    prompt = ENRICH_QUESTIONS.format(
        n_max=n_max,
        master_yaml=yaml.safe_dump(master.model_dump(), sort_keys=False, allow_unicode=True),
        facts_yaml=yaml.safe_dump(facts.model_dump(), sort_keys=False, allow_unicode=True),
        jd_text=jd_text,
    )
    try:
        parsed: EnrichQuestionsLLMOutput = llm.invoke(prompt)
    except ValidationError as exc:
        logger.error("generate_questions: LLM returned schema-invalid data: %s", exc)
        return []
    except Exception as exc:
        logger.error("generate_questions: LLM call failed: %s", exc)
        return []

    questions = [
        Question(area=q.area, question=q.question.strip(), why=q.why.strip())
        for q in parsed.questions[:n_max]
        if q.question.strip()
    ]
    logger.info("generate_questions: received %d grounded questions", len(questions))
    return questions


def polish_answer(
    question: Question,
    answer: str,
    master: ResumeMaster,
    jd_text: str,
) -> PolishedFactLLMOutput | None:
    """Polish a free-text answer into a resume-bullet + bucket classification."""
    role_ids = [r.id for r in master.experience]
    # A cheap keyword hint — send the first ~300 chars of the JD in case its
    # framing matters. The LLM already has the full JD context via question area.
    jd_keywords = jd_text[:300]
    prompt = ENRICH_POLISH.format(
        question=question.question,
        answer=answer.strip(),
        jd_keywords=jd_keywords,
        role_ids=", ".join(role_ids) if role_ids else "(none)",
    )
    llm = get_structured_llm(PolishedFactLLMOutput)
    try:
        parsed: PolishedFactLLMOutput = llm.invoke(prompt)
    except ValidationError as exc:
        logger.error("polish_answer: LLM returned schema-invalid data: %s", exc)
        return None
    except Exception as exc:
        logger.error("polish_answer: LLM call failed: %s", exc)
        return None

    # Guard: if LLM says extra_bullet but the role_id isn't in the master, demote to project.
    if parsed.bucket == "extra_bullet" and parsed.role_id not in role_ids:
        logger.warning(
            "polish_answer: LLM chose extra_bullet with unknown role_id %r; demoting to project",
            parsed.role_id,
        )
        parsed.bucket = "project"
        parsed.role_id = ""

    return parsed


# --- Persistence assembly -------------------------------------------------


def assemble_additions(
    plan: SessionPlan,
    *,
    today: date | None = None,
    existing_ids: set[str] | None = None,
) -> tuple[list[FactItem], list[FactItem], list[str], list[str]]:
    """Split a `SessionPlan` into the four lists `append_to_facts` expects.

    IDs are minted as `enrich-{YYYYMMDD}-{n}` with collision avoidance against
    `existing_ids`. `source` is stamped with `enrich {YYYY-MM-DD}` for traceability.
    """
    stamp_date = today or date.today()
    id_prefix = f"enrich-{stamp_date.strftime('%Y%m%d')}"
    source = f"enrich {stamp_date.isoformat()}"
    used_ids: set[str] = set(existing_ids or set())

    def _mint_id() -> str:
        for n in range(1, 1000):
            candidate = f"{id_prefix}-{n}"
            if candidate not in used_ids:
                used_ids.add(candidate)
                return candidate
        raise RuntimeError("exhausted id suffixes 1..999 — clean up facts_bank")

    projects: list[FactItem] = []
    extra_bullets: list[FactItem] = []
    skills: list[str] = []
    certifications: list[str] = []

    for item in plan.items:
        text = item.text.strip()
        if not text:
            continue
        if item.bucket == "skill":
            skills.append(text)
        elif item.bucket == "certification":
            certifications.append(text)
        elif item.bucket == "extra_bullet":
            extra_bullets.append(
                FactItem(id=_mint_id(), text=text, role_id=item.role_id, source=source)
            )
        else:  # project (default)
            projects.append(FactItem(id=_mint_id(), text=text, source=source))

    return projects, extra_bullets, skills, certifications


def collect_existing_ids(bank: FactsBank) -> set[str]:
    """Every id in the facts bank — used for collision avoidance on minted ids."""
    ids: set[str] = set()
    ids.update(item.id for item in bank.projects)
    ids.update(item.id for item in bank.extra_bullets)
    return ids


# --- Interactive session --------------------------------------------------
#
# Kept here alongside the pure LLM helpers so `run`'s auto-enrich path and any
# future non-CLI caller (server, tests) can reuse the same loop. User
# interaction goes through the injected `Prompter` seam.


def run_interactive_session(
    master: ResumeMaster,
    facts: FactsBank,
    jd_text: str,
    *,
    max_questions: int = 5,
    prompter: Prompter,
) -> SessionPlan:
    """Interactive enrichment session: ask → answer → polish → accept/edit/reject.

    Returns a `SessionPlan` with accepted items. Caller is responsible for
    persisting the plan via `assemble_additions` + `facts_bank.append_to_facts`.
    """
    with prompter.status("[bold cyan]Generating interview questions..."):
        questions = generate_questions(master, facts, jd_text, n_max=max_questions)

    if not questions:
        prompter.panel(
            "The LLM didn't surface any gap-worthy questions. Either your "
            "master already covers this JD, or the question-generation call "
            "failed (run with --verbose to see).",
            title="No questions",
            style="yellow",
        )
        return SessionPlan()

    prompter.panel(
        f"[bold]{len(questions)} question(s) to discuss.[/bold]\n\n"
        "[dim]For each question: answer with facts and metrics — e.g. "
        '"I built 50+ endpoints serving 2M requests/day" — not with instructions. '
        "Type 'skip' to skip, 'quit' to end early.[/dim]",
        title="Enrichment session",
        style="cyan",
    )

    plan = SessionPlan()
    total = len(questions)
    for i, question in enumerate(questions, 1):
        prompter.render_question(question, index=i, total=total)
        answer = prompter.text("[bold]>[/bold]", default="")
        if answer.lower() == "quit":
            break
        if not answer or answer.lower() == "skip":
            continue

        with prompter.status("[bold cyan]Polishing..."):
            polished = polish_answer(question, answer, master, jd_text)
        if polished is None:
            prompter.notice("Polish step failed — skipping this question.", style="red")
            continue

        prompter.render_polished(polished)

        choice = prompter.choose(
            "[a]ccept / [e]dit / [r]eject / [s]kip / [q]uit",
            choices=["a", "e", "r", "s", "q"],
            default="a",
        )
        if choice == "q":
            break
        if choice in ("r", "s"):
            continue
        final_text = polished.polished_text
        if choice == "e":
            edited = prompter.text("[bold]Your wording[/bold]", default=final_text)
            final_text = edited or final_text
        plan.items.append(
            AcceptedItem(
                text=final_text,
                bucket=polished.bucket,
                role_id=polished.role_id,
            )
        )

    return plan
