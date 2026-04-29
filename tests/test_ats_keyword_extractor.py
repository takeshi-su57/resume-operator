"""Tests for the LLM keyword extractor (#81).

Mocks the LLM entirely — we're testing that the extractor correctly promotes
validated LLM output into `SkillCountRow`s, caps per category, and derives
the back-compat `keyword_matches` / `keyword_gaps` lists.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lucky_resume.state import SkillCountRow
from lucky_resume.tools.ats_keyword_extractor import (
    MAX_HARD_SKILLS,
    MAX_SOFT_SKILLS,
    ATSKeywordsLLMOutput,
    _SkillCountLLM,
    derive_matches_and_gaps,
    extract_keywords,
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


class TestExtractKeywords:
    @patch("lucky_resume.tools.ats_keyword_extractor.get_structured_llm")
    def test_promotes_llm_rows_to_state_rows(self, mock_get_llm: MagicMock) -> None:
        mock_get_llm.return_value = _make_llm(
            ATSKeywordsLLMOutput(
                hard_skills=[
                    _SkillCountLLM(name="Python", resume_count=4, jd_count=2),
                    _SkillCountLLM(name="Kubernetes", resume_count=0, jd_count=3),
                ],
                soft_skills=[
                    _SkillCountLLM(name="Mentoring", resume_count=1, jd_count=1),
                ],
            )
        )

        hard, soft = extract_keywords("resume text", "jd text")

        assert len(hard) == 2
        assert hard[0].name == "Python"
        assert hard[0].resume_count == 4
        assert hard[1].name == "Kubernetes"
        assert hard[1].jd_count == 3
        assert len(soft) == 1
        assert soft[0].name == "Mentoring"

    @patch("lucky_resume.tools.ats_keyword_extractor.get_structured_llm")
    def test_trims_to_max(self, mock_get_llm: MagicMock) -> None:
        """A LLM that drifts past the 25/15 cap still comes back under the cap."""
        hard = [
            _SkillCountLLM(name=f"hard{i}", resume_count=1, jd_count=1)
            for i in range(MAX_HARD_SKILLS * 2)
        ]
        soft = [
            _SkillCountLLM(name=f"soft{i}", resume_count=1, jd_count=1)
            for i in range(MAX_SOFT_SKILLS * 2)
        ]
        mock_get_llm.return_value = _make_llm(
            ATSKeywordsLLMOutput(hard_skills=hard, soft_skills=soft)
        )
        h, s = extract_keywords("r", "j")
        assert len(h) == MAX_HARD_SKILLS
        assert len(s) == MAX_SOFT_SKILLS

    @patch("lucky_resume.tools.ats_keyword_extractor.get_structured_llm")
    def test_clamps_negative_counts(self, mock_get_llm: MagicMock) -> None:
        """A LLM that emits -1 gets clamped to 0 — negative counts are always a bug."""
        mock_get_llm.return_value = _make_llm(
            ATSKeywordsLLMOutput(
                hard_skills=[_SkillCountLLM(name="Python", resume_count=-5, jd_count=2)],
            )
        )
        hard, _ = extract_keywords("r", "j")
        assert hard[0].resume_count == 0

    @patch("lucky_resume.tools.ats_keyword_extractor.get_structured_llm")
    def test_drops_empty_names(self, mock_get_llm: MagicMock) -> None:
        mock_get_llm.return_value = _make_llm(
            ATSKeywordsLLMOutput(
                hard_skills=[
                    _SkillCountLLM(name="", resume_count=1, jd_count=1),
                    _SkillCountLLM(name="   ", resume_count=1, jd_count=1),
                    _SkillCountLLM(name="Python", resume_count=1, jd_count=1),
                ]
            )
        )
        hard, _ = extract_keywords("r", "j")
        assert len(hard) == 1
        assert hard[0].name == "Python"

    @patch("lucky_resume.tools.ats_keyword_extractor.get_structured_llm")
    def test_llm_failure_returns_empty_lists(self, mock_get_llm: MagicMock) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API down"))
        hard, soft = extract_keywords("r", "j")
        assert hard == []
        assert soft == []

    def test_empty_inputs_return_empty(self) -> None:
        assert extract_keywords("", "jd") == ([], [])
        assert extract_keywords("resume", "") == ([], [])
        assert extract_keywords("", "") == ([], [])


class TestDeriveMatchesAndGaps:
    def test_matches_need_both_sides(self) -> None:
        rows = [
            SkillCountRow(name="Python", resume_count=2, jd_count=1),
            SkillCountRow(name="Rust", resume_count=1, jd_count=0),  # not in JD — not a match
        ]
        matches, gaps = derive_matches_and_gaps(rows, [])
        assert matches == ["Python"]
        # "Rust" is neither a match (JD doesn't ask) nor a gap (resume has it).
        assert gaps == []

    def test_gaps_need_jd_present_resume_zero(self) -> None:
        rows = [
            SkillCountRow(name="Kubernetes", resume_count=0, jd_count=3),
            SkillCountRow(name="Python", resume_count=2, jd_count=2),
        ]
        matches, gaps = derive_matches_and_gaps(rows, [])
        assert gaps == ["Kubernetes"]
        assert matches == ["Python"]

    def test_soft_skills_flow_through(self) -> None:
        hard = [SkillCountRow(name="Python", resume_count=1, jd_count=1)]
        soft = [SkillCountRow(name="Mentoring", resume_count=0, jd_count=2)]
        matches, gaps = derive_matches_and_gaps(hard, soft)
        assert matches == ["Python"]
        assert gaps == ["Mentoring"]

    def test_both_sides_zero_is_skipped(self) -> None:
        """A row where neither side has a mention shouldn't appear in either
        bucket — it's noise from the LLM."""
        rows = [SkillCountRow(name="Noise", resume_count=0, jd_count=0)]
        matches, gaps = derive_matches_and_gaps(rows, [])
        assert matches == [] and gaps == []
