"""Tests for the ats_score node (#81 multi-dimensional orchestrator).

Mocks the three sub-passes (`check_contact`/etc. are pure, but we mock
the LLM-facing `extract_keywords` and `check_tone` to keep tests
deterministic). Assertions focus on the assembled `ATSReport` — field
presence, composite-score clamping, empty-resume short-circuit.
"""

from unittest.mock import MagicMock, patch

from lucky_resume.nodes.ats_score import ats_score, ats_score_tailored
from lucky_resume.state import (
    ATSReport,
    ResumeOptimizerState,
    SkillCountRow,
    TailoredItem,
    TailoredResume,
    ToneFlag,
)


def _patch_llm_passes(
    *,
    hard: list[SkillCountRow] | None = None,
    soft: list[SkillCountRow] | None = None,
    tone: list[ToneFlag] | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Configure mocked return values for the two LLM-facing passes."""
    hard_out = hard if hard is not None else []
    soft_out = soft if soft is not None else []
    tone_out = tone if tone is not None else []
    return (hard_out, soft_out), tone_out


class TestAtsScoreOrchestrator:
    @patch("lucky_resume.nodes.ats_score.check_tone")
    @patch("lucky_resume.nodes.ats_score.extract_keywords")
    def test_assembles_full_report(
        self,
        mock_extract: MagicMock,
        mock_tone: MagicMock,
        sample_state: ResumeOptimizerState,
    ) -> None:
        hard = [
            SkillCountRow(name="Python", resume_count=3, jd_count=2),
            SkillCountRow(name="Kubernetes", resume_count=0, jd_count=3),
        ]
        soft = [SkillCountRow(name="Mentoring", resume_count=1, jd_count=1)]
        mock_extract.return_value = (hard, soft)
        mock_tone.return_value = [ToneFlag(phrase="results-driven", line="x", suggestion="y")]

        result = ats_score(sample_state)

        assert "ats_score" in result
        report: ATSReport = result["ats_score"]
        # Structural checks ran.
        assert report.word_count > 0
        # Keyword tables are on the report.
        assert len(report.hard_skills) == 2
        assert len(report.soft_skills) == 1
        # Back-compat fields derived.
        assert "Python" in report.keyword_matches
        assert "Kubernetes" in report.keyword_gaps
        # Tone flag flowed through.
        assert len(report.tone_flags) == 1
        assert report.tone_flags[0].phrase == "results-driven"
        # Composite is a float in [0, 1].
        assert 0.0 <= report.score <= 1.0

    @patch("lucky_resume.nodes.ats_score.check_tone")
    @patch("lucky_resume.nodes.ats_score.extract_keywords")
    def test_composite_with_perfect_inputs_is_near_one(
        self,
        mock_extract: MagicMock,
        mock_tone: MagicMock,
        sample_state: ResumeOptimizerState,
    ) -> None:
        """A resume that covers every JD skill, has a perfect title match, all
        contact fields, all sections, in-range word count, and zero tone flags
        should approach 1.0 (modulo measurable-results which depends on raw text).
        """
        hard = [SkillCountRow(name="Python", resume_count=3, jd_count=1)]
        soft = [SkillCountRow(name="Mentoring", resume_count=1, jd_count=1)]
        mock_extract.return_value = (hard, soft)
        mock_tone.return_value = []
        # Give the master a job-title exact match by crafting the JD to contain it.
        sample_state.job_description.raw_text = (
            "Position: Senior Engineer\n\nWe want Python and mentoring."
        )

        result = ats_score(sample_state)
        report: ATSReport = result["ats_score"]
        assert report.job_title.exact_match
        assert report.hard_skills[0].name == "Python"
        # Composite should reflect the strong match — at least 0.6 even with
        # measurable_results contributing sub-optimally.
        assert report.score >= 0.6

    @patch("lucky_resume.nodes.ats_score.check_tone")
    @patch("lucky_resume.nodes.ats_score.extract_keywords")
    def test_llm_failure_still_produces_report(
        self,
        mock_extract: MagicMock,
        mock_tone: MagicMock,
        sample_state: ResumeOptimizerState,
    ) -> None:
        """When both LLM passes fail and return empty, the node still assembles
        a report from structural checks alone — composite is lower but valid.
        """
        mock_extract.return_value = ([], [])
        mock_tone.return_value = []

        result = ats_score(sample_state)
        assert "ats_score" in result
        report: ATSReport = result["ats_score"]
        assert report.hard_skills == []
        assert report.soft_skills == []
        # Structural half still fills in.
        assert 0.0 <= report.score <= 1.0

    def test_empty_resume_data_short_circuits(self, sample_state: ResumeOptimizerState) -> None:
        sample_state.resume.raw_text = ""
        result = ats_score(sample_state)
        assert "errors" in result
        assert any("resume data is empty" in e for e in result["errors"])
        assert "ats_score" not in result


class TestAtsScoreTailored:
    @patch("lucky_resume.nodes.ats_score.check_tone")
    @patch("lucky_resume.nodes.ats_score.extract_keywords")
    def test_scores_tailored_text_not_master(
        self,
        mock_extract: MagicMock,
        mock_tone: MagicMock,
        sample_state: ResumeOptimizerState,
    ) -> None:
        mock_extract.return_value = (
            [SkillCountRow(name="Python", resume_count=1, jd_count=1)],
            [],
        )
        mock_tone.return_value = []
        sample_state.tailored_resume = TailoredResume(
            items=[
                TailoredItem(
                    source_id="master:exp-1-b1",
                    action="reword",
                    new_text="Tailored Python-leading bullet",
                )
            ],
            tailored_summary="Tailored summary",
        )

        result = ats_score_tailored(sample_state)
        assert "ats_score" in result
        # The orchestrator rendered the tailored text and passed it to
        # extract_keywords — we can verify via the call args.
        sent_resume_text = mock_extract.call_args.args[0]
        assert "Tailored summary" in sent_resume_text
        assert "Tailored Python-leading bullet" in sent_resume_text

    def test_no_tailored_items_is_noop(self, sample_state: ResumeOptimizerState) -> None:
        sample_state.tailored_resume = TailoredResume(items=[])
        result = ats_score_tailored(sample_state)
        assert result == {}
