"""Central state model for the resume optimization pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResumeData(BaseModel):
    """Structured resume data extracted from PDF."""

    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    experience: list[dict[str, str]] = Field(default_factory=list)
    education: list[dict[str, str]] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    raw_text: str = ""


class ExperienceBullet(BaseModel):
    """A single bullet on an experience entry with a stable ID."""

    id: str
    text: str


class ExperienceEntry(BaseModel):
    """One role on the master resume."""

    id: str
    role: str = ""
    company: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: list[ExperienceBullet] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)
    # Per-role tech list rendered as a `Tech: ...` line after the bullets (issue #68).
    # Optional — empty list means no tech line renders for this role.


class EducationEntry(BaseModel):
    """One education entry on the master resume."""

    id: str
    degree: str = ""
    school: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    details: str = ""


class Link(BaseModel):
    """A labeled URL on the resume header (Portfolio, LinkedIn, GitHub, …)."""

    label: str
    url: str


class SkillGroup(BaseModel):
    """A named group of skills rendered as a categorised SKILLS block (#68)."""

    category: str
    items: list[str] = Field(default_factory=list)


class ResumeMaster(BaseModel):
    """Hand-maintained master resume loaded from `master_resume.yaml`.

    Source of truth for all downstream pipeline work. Each experience bullet
    and entry carries a stable ID so tailoring (#026) can reference items
    deterministically.

    Fields added in #68 are all optional — existing `master_resume.yaml`
    files without them still load and render:
      - `headline` — tagline under the name
      - `links` — portfolio / LinkedIn / GitHub, shown on a second contact line
      - `skill_groups` — categorised skills; when non-empty it wins over the
        flat `skills` list for rendering (but `skills` is still consulted by
        the source_index so the tailor's fabrication guard keeps working)
    """

    name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[Link] = Field(default_factory=list)
    summary: str = ""
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skill_groups: list[SkillGroup] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    def all_skills(self) -> list[str]:
        """Every skill on this master, flattened across `skills` + `skill_groups`.

        Used by `source_index` so categorised skills keep producing the same
        `master:skill:<name>` IDs the tailor already validates against.
        """
        seen: set[str] = set()
        flat: list[str] = []
        for name in self.skills:
            if name and name not in seen:
                seen.add(name)
                flat.append(name)
        for group in self.skill_groups:
            for name in group.items:
                if name and name not in seen:
                    seen.add(name)
                    flat.append(name)
        return flat


class FactItem(BaseModel):
    """A project, achievement, or other bullet that didn't fit on the trimmed master."""

    id: str
    text: str
    role_id: str = ""  # optional: links to an `ExperienceEntry.id` for spliceable bullets
    source: str = ""  # optional: e.g. "enrich 2026-04-21" — where this item came from
    overrides: str = ""
    # Optional: when non-empty, this fact *replaces* the master entry with this
    # `source_id` in the source index — the tailor sees the polished text instead
    # of the original hand-authored one. Populated by the `apply_approvals` node
    # when the user accepts a `rewrite_master` proposal (#78). Deleting this
    # fact brings the original master entry back; master is strictly read-only.


class FactsBank(BaseModel):
    """Optional pool of items beyond the master resume.

    During tailoring (#026), the optimizer may pull items from here into the
    output when they are a strong match for the JD. Everything is optional —
    missing file or empty bank is a valid state.
    """

    projects: list[FactItem] = Field(default_factory=list)
    extra_bullets: list[FactItem] = Field(default_factory=list)
    skills_beyond_master: list[str] = Field(default_factory=list)
    certifications_beyond_master: list[str] = Field(default_factory=list)


class JobDescription(BaseModel):
    """Structured job description data."""

    title: str = ""
    company: str = ""
    requirements: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    raw_text: str = ""


class ContactCheck(BaseModel):
    """#81: which contact fields the resume surfaces — what industry ATS
    reviewers flag for completeness."""

    email_present: bool = False
    phone_present: bool = False
    address_present: bool = False


class SectionCheck(BaseModel):
    """#81: presence of the four canonical resume sections."""

    summary: bool = False
    experience: bool = False
    education: bool = False
    skills: bool = False


class JobTitleMatch(BaseModel):
    """#81: whether the JD's job title appears on the resume. ATS keyword
    scanners weight exact-title matches heavily — missing it drops rank."""

    exact_match: bool = False
    partial_match: bool = False  # substring / fuzzy
    jd_title: str = ""
    resume_titles: list[str] = Field(default_factory=list)


class SkillCountRow(BaseModel):
    """One row in the hard-skill or soft-skill comparison table — the side-by-side
    count of a skill mention on the resume vs. in the JD."""

    name: str
    resume_count: int = 0
    jd_count: int = 0


class ToneFlag(BaseModel):
    """A cliche or negative phrase flagged for rewrite ("results-driven",
    "passionate about", …)."""

    phrase: str
    line: str = ""
    suggestion: str = ""


class ATSReport(BaseModel):
    """Multi-dimensional ATS compatibility report (#81) — replaces the single
    ATSScore float while preserving its fields as back-compat aliases.

    Dimensions split into:
      - structural (deterministic): contact, sections, job title, word count,
        measurable-results count
      - keyword (LLM-extracted, then compared): hard_skills, soft_skills
      - qualitative (LLM): tone_flags, level_match_reasoning
      - composite (derived): ``score`` is a weighted sum exposed for the #44
        skip gate and per-iteration display.
    """

    # Composite numeric score — derived, same 0.0-1.0 contract as the old ATSScore.
    score: float = 0.0
    # Prose summary the CLI renders alongside the table.
    reasoning: str = ""

    # Structural checks (deterministic).
    contact: ContactCheck = Field(default_factory=ContactCheck)
    sections: SectionCheck = Field(default_factory=SectionCheck)
    job_title: JobTitleMatch = Field(default_factory=JobTitleMatch)
    measurable_results_count: int = 0
    word_count: int = 0
    word_count_ok: bool = False  # within 400-1000

    # Keyword analysis (LLM-extracted, deterministic comparison).
    hard_skills: list[SkillCountRow] = Field(default_factory=list)
    soft_skills: list[SkillCountRow] = Field(default_factory=list)

    # Qualitative (LLM).
    tone_flags: list[ToneFlag] = Field(default_factory=list)
    level_match_reasoning: str = ""

    # Back-compat for #78 and earlier callers that expect these fields on the ATS object.
    # Populated by the orchestrator from hard_skills + soft_skills.
    keyword_matches: list[str] = Field(default_factory=list)
    keyword_gaps: list[str] = Field(default_factory=list)


# Back-compat alias — pre-#81 code imports `ATSScore`. One-release deprecation
# window, then remove in the release after.
ATSScore = ATSReport


class GapAnalysis(BaseModel):
    """Resume gap analysis relative to job description."""

    gaps: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class OptimizedResume(BaseModel):
    """Optimized resume content ready for PDF generation."""

    sections: dict[str, str] = Field(default_factory=dict)
    changes_made: list[str] = Field(default_factory=list)


class TailoredItem(BaseModel):
    """A single per-item tailoring decision.

    Every tailored item references a stable ID in the master resume or facts
    bank — this is the fabrication guardrail (#026). The optimizer cannot
    synthesize text that isn't traceable back to a source.

    `source_id` format:
      - `master:exp-1`                → an experience role header (summary of that entry)
      - `master:exp-1-b1`             → a specific bullet on a role
      - `master:edu-1`                → an education entry
      - `master:skill:Python`         → a skill
      - `master:cert:AWS`             → a certification
      - `master:summary`              → the top-of-resume summary
      - `facts:proj-1`                → a project from the facts bank
      - `facts:extra-1`               → an extra bullet from the facts bank
      - `facts:skill:Docker`          → a skill from the facts bank
      - `facts:cert:CKAD`             → a cert from the facts bank
    """

    source_id: str
    action: str = "keep"  # one of: keep | reword | drop
    original_text: str = ""
    new_text: str = ""  # only meaningful when action == "reword"


class TailoredResume(BaseModel):
    """Structured tailored output — a list of per-item decisions, not free-form text.

    `tailored_summary` is a dedicated JD-crafted 2-3 sentence opener (issue #66).
    `tailored_headline` is the JD-crafted tagline under the name (issue #70).
    Both are free-form fields filled by `optimize_content` per run; the renderer
    prefers them over the static master equivalents when non-empty.
    """

    items: list[TailoredItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    tailored_summary: str = ""
    tailored_headline: str = ""

    def kept_or_reworded(self) -> list[TailoredItem]:
        return [i for i in self.items if i.action in {"keep", "reword"}]


# --- #78 iterative tailor loop -------------------------------------------
#
# The approval loop produces `Proposal` items from the LLM; the user gates each
# through a three-button UX (Yes/No/Fix). Accepted proposals land in the facts
# bank (persisted). Rejected proposals land in `rejected_suggestions` on state
# (per-run only) so the LLM doesn't re-propose the same idea on the next loop
# iteration.


class Proposal(BaseModel):
    """One LLM-generated suggestion the user can accept, reject, or refine (#78).

    Each proposal cites a `grounding_source_id` so the user has an anchor when
    deciding whether to approve — especially for the fabrication-sensitive
    `new_fact` kind, which extrapolates from an existing source rather than
    polishing one directly.
    """

    kind: str  # one of: rewrite_master | rewrite_fact | new_fact
    grounding_source_id: str  # e.g. "master:exp-2-b3" or "facts:enrich-20260423-1"
    original_text: str = ""  # canonical text at grounding_source_id (empty for new_fact)
    proposed_text: str
    rationale: str = ""  # short LLM note on why this helps JD alignment
    target_role_id: str = ""  # for new_fact: which master role the bullet belongs under


class RejectedSuggestion(BaseModel):
    """A proposal the user declined on this run. Passed back to `propose_changes`
    on the next iteration so the LLM avoids re-proposing the same idea (#78).
    """

    kind: str
    grounding_source_id: str
    rejected_text: str
    user_reason: str = ""


class ResumeOptimizerState(BaseModel):
    """Central state flowing through the LangGraph pipeline."""

    # Inputs
    resume_path: str = ""
    master_path: str = ""
    facts_path: str = ""
    style_path: str = ""  # optional StyleTemplate YAML (#72)
    job_description_path: str = ""
    job_description_text: str = ""

    # Parsed data
    resume: ResumeData = Field(default_factory=ResumeData)
    master: ResumeMaster = Field(default_factory=ResumeMaster)
    facts: FactsBank = Field(default_factory=FactsBank)
    job_description: JobDescription = Field(default_factory=JobDescription)

    # Analysis
    ats_score: ATSScore = Field(default_factory=ATSScore)
    gap_analysis: GapAnalysis = Field(default_factory=GapAnalysis)

    # Optimization
    optimized_resume: OptimizedResume = Field(default_factory=OptimizedResume)
    tailored_resume: TailoredResume = Field(default_factory=TailoredResume)

    # #78 iterative tailor loop — all ephemeral, per-run only.
    current_iteration: int = 0  # 1-indexed, bumped at the start of each loop pass
    max_iterations: int = 3
    # Best (tailored_resume, ats_score) seen so far — used when the user hits the
    # iteration cap and chooses to render instead of continuing.
    best_tailored_so_far: TailoredResume = Field(default_factory=TailoredResume)
    best_score_so_far: float = 0.0
    # Populated by `propose_changes` each iteration; cleared after the user gates it.
    proposals: list[Proposal] = Field(default_factory=list)
    # Populated by `approval_flow` when the user accepts / rejects; `apply_approvals`
    # drains `approved_proposals` into facts_bank at end of iteration.
    approved_proposals: list[Proposal] = Field(default_factory=list)
    rejected_suggestions: list[RejectedSuggestion] = Field(default_factory=list)
    # The user's decision on the current iteration's ATS score.
    user_accepted_tailored: bool = False
    # Headless mode: skip the loop entirely, behave like the pre-#78 single-pass
    # tailor. Used for CI / batch / `--no-approve`.
    skip_approval_loop: bool = False

    # Output
    output_dir: str = ""  # per-application folder (data/applications/{date}_{slug}/)
    output_path: str = ""  # PDF path (typically `{output_dir}/resume.pdf`)
    report: dict[str, object] = Field(default_factory=dict)

    # Tracking
    errors: list[str] = Field(default_factory=list)
