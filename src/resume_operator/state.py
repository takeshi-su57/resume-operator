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


class EducationEntry(BaseModel):
    """One education entry on the master resume."""

    id: str
    degree: str = ""
    school: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    details: str = ""


class ResumeMaster(BaseModel):
    """Hand-maintained master resume loaded from `master_resume.yaml`.

    Source of truth for all downstream pipeline work. Each experience bullet
    and entry carries a stable ID so tailoring (#026) can reference items
    deterministically.
    """

    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class FactItem(BaseModel):
    """A project, achievement, or other bullet that didn't fit on the trimmed master."""

    id: str
    text: str
    role_id: str = ""  # optional: links to an `ExperienceEntry.id` for spliceable bullets


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


class ResumeOptimizerState(BaseModel):
    """Central state flowing through the LangGraph pipeline."""

    # Inputs
    resume_path: str = ""
    master_path: str = ""
    facts_path: str = ""
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

    # Output
    output_path: str = ""
    report: dict[str, object] = Field(default_factory=dict)

    # Tracking
    errors: list[str] = Field(default_factory=list)
