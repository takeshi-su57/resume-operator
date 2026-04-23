"""Node: Score resume ATS compatibility against job description."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from resume_operator.prompts.ats_scoring import ATS_SCORE
from resume_operator.state import ATSScore, ResumeOptimizerState
from resume_operator.tools.llm_provider import get_structured_llm

logger = logging.getLogger(__name__)


class ATSScoreLLMOutput(BaseModel):
    """Schema handed to `with_structured_output` — the LLM fills this in directly."""

    score: float = Field(..., description="ATS compatibility score, 0.0 to 1.0")
    reasoning: str = Field(..., description="Short justification of the score")
    keyword_matches: list[str] = Field(default_factory=list)
    keyword_gaps: list[str] = Field(default_factory=list)


def ats_score(state: ResumeOptimizerState) -> dict[str, Any]:
    """Score how well the resume matches the job description for ATS systems.

    Compares resume keywords, experience, and skills against job requirements.
    Returns a score (0.0-1.0), keyword matches, keyword gaps, and reasoning.
    """
    logger.info("ats_score: starting")
    errors: list[str] = list(state.errors)

    if not state.resume.raw_text:
        logger.warning("ats_score: skipping — resume data is empty (parse_resume may have failed)")
        errors.append("ats_score: skipping — resume data is empty")
        return {"errors": errors}

    try:
        parsed = _run_scoring(
            resume_json=state.resume.model_dump_json(),
            jd_text=state.job_description.raw_text,
            label="ats_score",
        )
    except _ATSScoreError as failure:
        errors.append(failure.error)
        return {"errors": errors}

    return _build_result(parsed, errors=errors, prior=state.errors, label="ats_score")


def ats_score_tailored(state: ResumeOptimizerState) -> dict[str, Any]:
    """Score the tailored output against the JD (#78 iterative loop).

    Unlike `ats_score` (which scores the raw master), this node scores what
    the candidate would see in the generated PDF: kept/reworded items from
    `state.tailored_resume`, with the dedicated tailored headline + summary
    when present. The resulting score is what the user's accept/continue
    gate in the CLI reads.

    When no tailored items exist (optimization skipped or failed) the node
    leaves `state.ats_score` alone so the caller still sees the initial
    master-based score.
    """
    logger.info("ats_score_tailored: starting")
    errors: list[str] = list(state.errors)

    if not state.tailored_resume.items:
        logger.info("ats_score_tailored: no tailored items — leaving prior ats_score untouched")
        return {}

    tailored_text = _render_tailored_as_text(state)
    if not tailored_text.strip():
        logger.warning("ats_score_tailored: rendered tailored text is empty — skipping")
        return {}

    try:
        parsed = _run_scoring(
            resume_json=tailored_text,
            jd_text=state.job_description.raw_text,
            label="ats_score_tailored",
        )
    except _ATSScoreError as failure:
        errors.append(failure.error)
        return {"errors": errors}

    return _build_result(parsed, errors=errors, prior=state.errors, label="ats_score_tailored")


# --- internals ------------------------------------------------------------


class _ATSScoreError(Exception):
    def __init__(self, error: str) -> None:
        super().__init__(error)
        self.error = error


def _run_scoring(*, resume_json: str, jd_text: str, label: str) -> ATSScoreLLMOutput:
    """Call the ATS scoring LLM; raise `_ATSScoreError` on any failure so
    both public entry points share the same error-recording shape.
    """
    try:
        llm = get_structured_llm(ATSScoreLLMOutput)
        prompt = ATS_SCORE.format(resume_json=resume_json, job_description=jd_text)
        logger.debug("%s: LLM prompt: %s", label, prompt)
        parsed: ATSScoreLLMOutput = llm.invoke(prompt)
        logger.debug("%s: LLM response: %s", label, parsed.model_dump_json())
        return parsed
    except ValidationError as exc:
        logger.error("%s: LLM returned schema-invalid data: %s", label, exc)
        raise _ATSScoreError(f"{label}: LLM returned schema-invalid data: {exc}") from exc
    except Exception as exc:
        logger.error("%s: LLM call failed: %s", label, exc)
        raise _ATSScoreError(f"{label}: LLM call failed: {exc}") from exc


def _build_result(
    parsed: ATSScoreLLMOutput, *, errors: list[str], prior: list[str], label: str
) -> dict[str, Any]:
    score = max(0.0, min(1.0, float(parsed.score)))
    result_score = ATSScore(
        score=score,
        reasoning=parsed.reasoning,
        keyword_matches=list(parsed.keyword_matches),
        keyword_gaps=list(parsed.keyword_gaps),
    )
    logger.info(
        "%s: completed — score=%.2f, matches=%d, gaps=%d",
        label,
        result_score.score,
        len(result_score.keyword_matches),
        len(result_score.keyword_gaps),
    )
    result: dict[str, Any] = {"ats_score": result_score}
    if errors != list(prior):
        result["errors"] = errors
    return result


def _render_tailored_as_text(state: ResumeOptimizerState) -> str:
    """Flatten the tailored output into a plain-text resume — same shape
    `ats_score` expects, so we can reuse the same LLM prompt.
    """
    tailored = state.tailored_resume
    master = state.master
    lines: list[str] = []
    if master.name:
        lines.append(master.name)
    contact = " | ".join(x for x in (master.email, master.phone, master.location) if x)
    if contact:
        lines.append(contact)
    headline = tailored.tailored_headline or master.headline
    if headline:
        lines.append(headline)
    summary_text = tailored.tailored_summary or master.summary
    if summary_text:
        lines.extend(["", "SUMMARY", summary_text])

    # Group kept/reworded items by (kind, role) to reconstruct the rendered PDF's
    # structure. We don't need perfect fidelity — just enough for the LLM to see
    # what's on the page.
    bullets_by_role: dict[str, list[str]] = {}
    skills: list[str] = []
    certifications: list[str] = []
    education: list[str] = []
    standalone: list[str] = []
    for item in tailored.kept_or_reworded():
        text = item.new_text or item.original_text
        if item.source_id.startswith("master:skill:") or item.source_id.startswith("facts:skill:"):
            skills.append(text)
        elif item.source_id.startswith("master:cert:") or item.source_id.startswith("facts:cert:"):
            certifications.append(text)
        elif item.source_id.startswith("master:edu-"):
            education.append(text)
        elif item.source_id.startswith("master:exp-"):
            # bullets: master:exp-1-b2 → role_id "exp-1"
            body = item.source_id[len("master:") :]
            role_id = body.rsplit("-b", 1)[0] if "-b" in body else body
            bullets_by_role.setdefault(role_id, []).append(text)
        elif item.source_id == "master:summary":
            # Summary was already captured above via tailored.tailored_summary path.
            continue
        else:
            # facts bullets, projects, extras — fall into standalone unless the
            # source index told us a role_id. We don't carry that through here;
            # list them as standalone.
            standalone.append(text)

    if bullets_by_role:
        lines.extend(["", "EXPERIENCE"])
        for role in master.experience:
            bullets = bullets_by_role.get(role.id)
            if not bullets:
                continue
            header = " | ".join(
                p for p in (role.role, role.company, f"{role.start_date} - {role.end_date}") if p
            )
            lines.append(header)
            lines.extend(f"- {b}" for b in bullets)
    if standalone:
        lines.extend(["", "PROJECTS / EXTRAS"])
        lines.extend(f"- {t}" for t in standalone)
    if skills:
        lines.extend(["", "SKILLS", ", ".join(skills)])
    if education:
        lines.extend(["", "EDUCATION"])
        lines.extend(f"- {e}" for e in education)
    if certifications:
        lines.extend(["", "CERTIFICATIONS"])
        lines.extend(f"- {c}" for c in certifications)

    return "\n".join(lines)
