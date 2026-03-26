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
    job_description_path: str = ""
    job_description_text: str = ""

    # Parsed data
    resume: ResumeData = Field(default_factory=ResumeData)
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
