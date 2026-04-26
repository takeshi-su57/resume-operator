"""Node: Score resume ATS compatibility against job description.

Assembles the multi-dimensional `ATSReport` (#81) from three passes:

  - `tools/ats_checks.py` — deterministic: contact info, sections, job
    title match, word count, measurable-results count.
  - `tools/ats_keyword_extractor.py` — single LLM call: hard-skill and
    soft-skill tables with resume-vs-JD counts per skill.
  - `tools/ats_tone_checker.py` — single LLM call: cliche / vague-
    positive phrase flags.

The composite `score` is a weighted sum over the above; weights are
tunable via `Settings.ats_weight_*` env vars. The same orchestrator
runs for both `ats_score` (scores the master resume, pre-tailor) and
`ats_score_tailored` (scores the tailored output inside #78's loop).
"""

from __future__ import annotations

import logging
from typing import Any

from resume_operator.config import get_settings
from resume_operator.events import node_span
from resume_operator.state import (
    ATSReport,
    ContactCheck,
    JobTitleMatch,
    ResumeOptimizerState,
    SectionCheck,
    SkillCountRow,
)
from resume_operator.tools.ats_checks import (
    check_contact,
    check_job_title,
    check_sections,
    count_measurable_results,
    count_words,
    word_count_ok,
)
from resume_operator.tools.ats_keyword_extractor import (
    derive_matches_and_gaps,
    extract_keywords,
)
from resume_operator.tools.ats_tone_checker import check_tone

logger = logging.getLogger(__name__)


# Industry-standard target for measurable-results — normalize the count against
# this when feeding it into the composite. More than 8 caps at 1.0.
MEASURABLE_RESULTS_TARGET = 8


def ats_score(state: ResumeOptimizerState) -> dict[str, Any]:
    """Score the master resume against the JD and produce a full `ATSReport`."""
    with node_span("ats_score"):
        return _ats_score_body(state)


def _ats_score_body(state: ResumeOptimizerState) -> dict[str, Any]:
    logger.info("ats_score: starting")
    errors: list[str] = list(state.errors)

    if not state.resume.raw_text:
        logger.warning("ats_score: skipping — resume data is empty")
        errors.append("ats_score: skipping — resume data is empty")
        return {"errors": errors}

    report = _build_report(state, resume_text=state.resume.raw_text, label="ats_score")
    logger.info(
        "ats_score: completed — composite=%.2f, hard=%d, soft=%d, tone_flags=%d",
        report.score,
        len(report.hard_skills),
        len(report.soft_skills),
        len(report.tone_flags),
    )
    return {"ats_score": report}


def ats_score_tailored(state: ResumeOptimizerState) -> dict[str, Any]:
    """Score the tailored output against the JD (#78 iterative loop).

    Same orchestrator as `ats_score`, fed a text rendering of the tailored
    resume instead of the raw master. When no tailored items exist
    (optimization skipped or failed) the node leaves `state.ats_score` alone
    so the caller still sees the initial master-based score.
    """
    with node_span("ats_score_tailored"):
        return _ats_score_tailored_body(state)


def _ats_score_tailored_body(state: ResumeOptimizerState) -> dict[str, Any]:
    logger.info("ats_score_tailored: starting")

    if not state.tailored_resume.items:
        logger.info("ats_score_tailored: no tailored items — leaving prior ats_score untouched")
        return {}

    tailored_text = _render_tailored_as_text(state)
    if not tailored_text.strip():
        logger.warning("ats_score_tailored: rendered tailored text is empty — skipping")
        return {}

    report = _build_report(state, resume_text=tailored_text, label="ats_score_tailored")
    logger.info(
        "ats_score_tailored: completed — composite=%.2f, hard=%d, soft=%d, tone_flags=%d",
        report.score,
        len(report.hard_skills),
        len(report.soft_skills),
        len(report.tone_flags),
    )
    return {"ats_score": report}


# --- orchestrator ---------------------------------------------------------


def _build_report(state: ResumeOptimizerState, *, resume_text: str, label: str) -> ATSReport:
    """Run the three passes and assemble the composite score."""
    jd_text = state.job_description.raw_text

    # 1. Deterministic structural checks (no LLM).
    contact = check_contact(state.master, resume_text)
    sections = check_sections(state.master, resume_text)
    job_title = check_job_title(state.master, jd_text)
    measurable = count_measurable_results(resume_text)
    wc = count_words(resume_text)
    wc_ok = word_count_ok(wc)

    # 2. LLM keyword extractor.
    hard, soft = extract_keywords(resume_text, jd_text)
    matches, gaps = derive_matches_and_gaps(hard, soft)

    # 3. LLM tone checker.
    tone_flags = check_tone(resume_text)

    # 4. Composite score.
    composite = _composite_score(
        hard=hard,
        soft=soft,
        contact=contact,
        sections=sections,
        job_title=job_title,
        measurable=measurable,
        wc_ok=wc_ok,
        tone_flags_count=len(tone_flags),
    )
    reasoning = _reasoning_summary(
        composite=composite,
        hard=hard,
        soft=soft,
        job_title=job_title,
        measurable=measurable,
    )

    return ATSReport(
        score=composite,
        reasoning=reasoning,
        contact=contact,
        sections=sections,
        job_title=job_title,
        measurable_results_count=measurable,
        word_count=wc,
        word_count_ok=wc_ok,
        hard_skills=hard,
        soft_skills=soft,
        tone_flags=tone_flags,
        keyword_matches=matches,
        keyword_gaps=gaps,
    )


def _composite_score(
    *,
    hard: list[SkillCountRow],
    soft: list[SkillCountRow],
    contact: ContactCheck,
    sections: SectionCheck,
    job_title: JobTitleMatch,
    measurable: int,
    wc_ok: bool,
    tone_flags_count: int,
) -> float:
    """Weighted sum across the six sub-dimensions. Weights come from
    `Settings.ats_weight_*` — defaults sum to 1.0.
    """
    settings = get_settings()
    hard_sub = _coverage(hard)
    soft_sub = _coverage(soft)
    structural_sub = _structural_sub(contact, sections, wc_ok)
    title_sub = _title_sub(job_title)
    measurable_sub = (
        min(1.0, measurable / MEASURABLE_RESULTS_TARGET) if MEASURABLE_RESULTS_TARGET else 0.0
    )
    # Tone subscore: 1.0 with zero flags, 0.6 at 3 flags, 0.0 past ~6.
    tone_sub = max(0.0, 1.0 - (tone_flags_count * 0.15))

    composite = (
        settings.ats_weight_hard * hard_sub
        + settings.ats_weight_soft * soft_sub
        + settings.ats_weight_structural * structural_sub
        + settings.ats_weight_title * title_sub
        + settings.ats_weight_measurable * measurable_sub
        + settings.ats_weight_tone * tone_sub
    )
    return max(0.0, min(1.0, composite))


def _coverage(rows: list[SkillCountRow]) -> float:
    """Fraction of JD-requested skills the resume actually mentions.

    Denominator: skills where `jd_count >= 1`. Numerator: those same skills
    where `resume_count >= 1`. Returns 1.0 when the JD asks for nothing
    (no denominator) — the resume can't be faulted for missing what isn't
    asked for.
    """
    jd_skills = [r for r in rows if r.jd_count >= 1]
    if not jd_skills:
        return 1.0
    matched = sum(1 for r in jd_skills if r.resume_count >= 1)
    return matched / len(jd_skills)


def _structural_sub(contact: ContactCheck, sections: SectionCheck, wc_ok: bool) -> float:
    """Average of 8 boolean dimensions: 3 contact + 4 section + word_count_ok."""
    flags = [
        contact.email_present,
        contact.phone_present,
        contact.address_present,
        sections.summary,
        sections.experience,
        sections.education,
        sections.skills,
        wc_ok,
    ]
    return sum(1 for f in flags if f) / len(flags)


def _title_sub(job_title: JobTitleMatch) -> float:
    """Exact match scores 1.0; partial 0.5; no match 0.0."""
    if job_title.exact_match:
        return 1.0
    if job_title.partial_match:
        return 0.5
    return 0.0


def _reasoning_summary(
    *,
    composite: float,
    hard: list[SkillCountRow],
    soft: list[SkillCountRow],
    job_title: JobTitleMatch,
    measurable: int,
) -> str:
    """Short prose for the CLI — fills the ATSReport.reasoning field."""
    top_gaps = [r.name for r in hard if r.jd_count >= 1 and r.resume_count == 0][:5]
    top_matches = [r.name for r in hard if r.jd_count >= 1 and r.resume_count >= 1][:5]
    parts: list[str] = [f"Composite {composite:.0%}."]
    if job_title.exact_match:
        parts.append("Job title exact match.")
    elif job_title.partial_match:
        parts.append("Job title partial match.")
    elif job_title.jd_title:
        parts.append(f"Job title '{job_title.jd_title}' not on resume.")
    if top_matches:
        parts.append(f"Hard-skill matches: {', '.join(top_matches)}.")
    if top_gaps:
        parts.append(f"Hard-skill gaps: {', '.join(top_gaps)}.")
    parts.append(f"Measurable results count: {measurable}.")
    return " ".join(parts)


def _render_tailored_as_text(state: ResumeOptimizerState) -> str:
    """Flatten the tailored output into a plain-text resume — same shape
    `ats_score` consumes, so the orchestrator treats it identically to the
    master resume text.
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
            body = item.source_id[len("master:") :]
            role_id = body.rsplit("-b", 1)[0] if "-b" in body else body
            bullets_by_role.setdefault(role_id, []).append(text)
        elif item.source_id == "master:summary":
            continue
        else:
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
