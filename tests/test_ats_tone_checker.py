"""Tests for the LLM tone checker (#81)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lucky_resume.tools.ats_tone_checker import (
    MAX_TONE_FLAGS,
    ATSToneLLMOutput,
    _ToneFlagLLM,
    check_tone,
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


class TestCheckTone:
    @patch("lucky_resume.tools.ats_tone_checker.get_structured_llm")
    def test_promotes_flags(self, mock_get_llm: MagicMock) -> None:
        mock_get_llm.return_value = _make_llm(
            ATSToneLLMOutput(
                flags=[
                    _ToneFlagLLM(
                        phrase="results-driven",
                        line="Results-driven backend engineer.",
                        suggestion="Replace with a specific outcome.",
                    ),
                    _ToneFlagLLM(
                        phrase="passionate about",
                        line="Passionate about scalable systems.",
                        suggestion="Cite a scale metric.",
                    ),
                ]
            )
        )
        flags = check_tone("some resume text")
        assert len(flags) == 2
        assert flags[0].phrase == "results-driven"
        assert flags[0].suggestion == "Replace with a specific outcome."

    @patch("lucky_resume.tools.ats_tone_checker.get_structured_llm")
    def test_trims_to_max(self, mock_get_llm: MagicMock) -> None:
        raw = [
            _ToneFlagLLM(phrase=f"cliche{i}", line=f"line{i}", suggestion="fix")
            for i in range(MAX_TONE_FLAGS * 2)
        ]
        mock_get_llm.return_value = _make_llm(ATSToneLLMOutput(flags=raw))
        flags = check_tone("resume text")
        assert len(flags) == MAX_TONE_FLAGS

    @patch("lucky_resume.tools.ats_tone_checker.get_structured_llm")
    def test_drops_empty_phrases(self, mock_get_llm: MagicMock) -> None:
        mock_get_llm.return_value = _make_llm(
            ATSToneLLMOutput(
                flags=[
                    _ToneFlagLLM(phrase="", line="line"),
                    _ToneFlagLLM(phrase="   ", line="line"),
                    _ToneFlagLLM(phrase="real-one", line="line"),
                ]
            )
        )
        flags = check_tone("resume")
        assert len(flags) == 1
        assert flags[0].phrase == "real-one"

    @patch("lucky_resume.tools.ats_tone_checker.get_structured_llm")
    def test_llm_failure_returns_empty(self, mock_get_llm: MagicMock) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API down"))
        assert check_tone("resume") == []

    def test_empty_text_returns_empty(self) -> None:
        assert check_tone("") == []
        assert check_tone("   \n  ") == []
