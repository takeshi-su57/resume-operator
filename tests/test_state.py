"""Tests for state models."""

from resume_operator.state import (
    ATSScore,
    GapAnalysis,
    JobDescription,
    OptimizedResume,
    ResumeData,
    ResumeOptimizerState,
)


class TestResumeData:
    def test_defaults(self) -> None:
        data = ResumeData()
        assert data.name == ""
        assert data.skills == []
        assert data.experience == []

    def test_with_values(self, sample_resume: ResumeData) -> None:
        assert sample_resume.name == "Jane Smith"
        assert len(sample_resume.experience) == 2
        assert "Python" in sample_resume.skills


class TestJobDescription:
    def test_defaults(self) -> None:
        job = JobDescription()
        assert job.title == ""
        assert job.keywords == []

    def test_with_values(self, sample_job: JobDescription) -> None:
        assert sample_job.company == "BigCo"
        assert "Python" in sample_job.keywords


class TestResumeOptimizerState:
    def test_defaults(self) -> None:
        state = ResumeOptimizerState()
        assert state.resume_path == ""
        assert state.errors == []
        assert state.ats_score.score == 0.0

    def test_full_state(self, sample_state: ResumeOptimizerState) -> None:
        assert sample_state.resume.name == "Jane Smith"
        assert sample_state.ats_score.score == 0.72
        assert len(sample_state.gap_analysis.gaps) == 2


class TestATSScore:
    def test_defaults(self) -> None:
        score = ATSScore()
        assert score.score == 0.0
        assert score.keyword_matches == []


class TestGapAnalysis:
    def test_defaults(self) -> None:
        analysis = GapAnalysis()
        assert analysis.gaps == []
        assert analysis.suggestions == []


class TestOptimizedResume:
    def test_defaults(self) -> None:
        resume = OptimizedResume()
        assert resume.sections == {}
        assert resume.changes_made == []
