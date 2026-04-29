"""Shared test fixtures."""

import pytest

from lucky_resume.state import (
    ATSScore,
    EducationEntry,
    ExperienceBullet,
    ExperienceEntry,
    GapAnalysis,
    JobDescription,
    ResumeData,
    ResumeMaster,
    ResumeOptimizerState,
)


@pytest.fixture
def sample_resume() -> ResumeData:
    """Pre-built ResumeData with realistic test data."""
    return ResumeData(
        name="Jane Smith",
        email="jane@example.com",
        phone="555-0100",
        summary="Senior software engineer with 8 years of experience in Python and cloud.",
        experience=[
            {
                "title": "Senior Engineer",
                "company": "TechCorp",
                "dates": "2020-present",
                "description": "Led backend team, built microservices in Python.",
            },
            {
                "title": "Software Engineer",
                "company": "StartupInc",
                "dates": "2016-2020",
                "description": "Full-stack development with Django and React.",
            },
        ],
        education=[
            {
                "degree": "B.S. Computer Science",
                "institution": "State University",
                "dates": "2012-2016",
            }
        ],
        skills=["Python", "Django", "AWS", "Docker", "PostgreSQL"],
        certifications=["AWS Solutions Architect"],
        raw_text="Jane Smith\njane@example.com\n...",
    )


@pytest.fixture
def sample_job() -> JobDescription:
    """Pre-built JobDescription with realistic test data."""
    return JobDescription(
        title="Backend Engineer",
        company="BigCo",
        requirements=["5+ years Python", "Experience with microservices", "AWS or GCP"],
        responsibilities=["Design and build APIs", "Mentor junior engineers"],
        keywords=["Python", "microservices", "AWS", "Kubernetes", "CI/CD"],
        raw_text="Backend Engineer at BigCo...",
    )


@pytest.fixture
def sample_master() -> ResumeMaster:
    """Pre-built ResumeMaster with stable IDs, aligned with `sample_resume`."""
    return ResumeMaster(
        name="Jane Smith",
        email="jane@example.com",
        phone="555-0100",
        summary="Senior software engineer with 8 years of experience in Python and cloud.",
        experience=[
            ExperienceEntry(
                id="exp-1",
                role="Senior Engineer",
                company="TechCorp",
                start_date="2020",
                end_date="present",
                bullets=[
                    ExperienceBullet(id="exp-1-b1", text="Led backend team"),
                    ExperienceBullet(id="exp-1-b2", text="Built microservices in Python"),
                ],
            ),
            ExperienceEntry(
                id="exp-2",
                role="Software Engineer",
                company="StartupInc",
                start_date="2016",
                end_date="2020",
                bullets=[
                    ExperienceBullet(id="exp-2-b1", text="Full-stack development with Django")
                ],
            ),
        ],
        education=[
            EducationEntry(
                id="edu-1",
                degree="B.S. Computer Science",
                school="State University",
                start_date="2012",
                end_date="2016",
            )
        ],
        skills=["Python", "Django", "AWS"],
        certifications=["AWS Solutions Architect"],
    )


@pytest.fixture
def sample_state(
    sample_resume: ResumeData,
    sample_job: JobDescription,
    sample_master: ResumeMaster,
) -> ResumeOptimizerState:
    """Full ResumeOptimizerState with resume + master + job data populated."""
    return ResumeOptimizerState(
        resume_path="test_resume.pdf",
        job_description_path="test_job.txt",
        resume=sample_resume,
        master=sample_master,
        job_description=sample_job,
        ats_score=ATSScore(
            score=0.72,
            reasoning="Good Python match, missing Kubernetes.",
            keyword_matches=["Python", "AWS", "microservices"],
            keyword_gaps=["Kubernetes", "CI/CD"],
        ),
        gap_analysis=GapAnalysis(
            gaps=["No Kubernetes experience listed", "No CI/CD pipeline experience"],
            strengths=["Strong Python background", "AWS certified"],
            suggestions=["Add Docker/K8s projects", "Mention CI/CD in experience"],
        ),
    )
