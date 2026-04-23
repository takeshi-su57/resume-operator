"""Tests for state models."""

from resume_operator.state import (
    ATSScore,
    GapAnalysis,
    JobDescription,
    OptimizedResume,
    Proposal,
    RejectedSuggestion,
    ResumeData,
    ResumeOptimizerState,
    TailoredResume,
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


class TestIterativeLoopState:
    """#78: per-run state carried across loop iterations."""

    def test_defaults(self) -> None:
        state = ResumeOptimizerState()
        assert state.current_iteration == 0
        assert state.max_iterations == 3
        assert state.proposals == []
        assert state.approved_proposals == []
        assert state.rejected_suggestions == []
        assert state.user_accepted_tailored is False
        assert state.skip_approval_loop is False
        assert isinstance(state.best_tailored_so_far, TailoredResume)
        assert state.best_score_so_far == 0.0

    def test_proposal_requires_grounding(self) -> None:
        # Every proposal cites a grounding_source_id — the user's reality-check anchor.
        p = Proposal(
            kind="rewrite_master",
            grounding_source_id="master:exp-1-b1",
            original_text="Led team",
            proposed_text="Led backend team building Kubernetes-orchestrated services",
        )
        assert p.kind == "rewrite_master"
        assert p.grounding_source_id == "master:exp-1-b1"

    def test_rejected_suggestion_carries_reason(self) -> None:
        r = RejectedSuggestion(
            kind="new_fact",
            grounding_source_id="master:exp-2-b3",
            rejected_text="Led 50-cluster K8s migration",
            user_reason="I never used K8s — only ECS",
        )
        assert r.user_reason == "I never used K8s — only ECS"
