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


class ATSScore(BaseModel):
    """ATS compatibility score and analysis."""

    score: float = 0.0
    reasoning: str = ""
    keyword_matches: list[str] = Field(default_factory=list)
    keyword_gaps: list[str] = Field(default_factory=list)


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

    # Output
    output_dir: str = ""  # per-application folder (data/applications/{date}_{slug}/)
    output_path: str = ""  # PDF path (typically `{output_dir}/resume.pdf`)
    report: dict[str, object] = Field(default_factory=dict)

    # Tracking
    errors: list[str] = Field(default_factory=list)
