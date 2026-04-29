"""Tests for the optimize_content node — per-item tailoring with fabrication guard."""

from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from lucky_resume.nodes.optimize_content import (
    TailoredItemLLM,
    TailoredResumeLLMOutput,
    optimize_content,
)
from lucky_resume.state import ResumeOptimizerState

VALID_OUTPUT = TailoredResumeLLMOutput(
    tailored_headline="Senior Backend Engineer · 8+ years · Python, AWS",
    tailored_summary="Senior engineer with 8+ years shipping Python/AWS backends.",
    items=[
        TailoredItemLLM(
            source_id="master:exp-1-b1",
            action="reword",
            original_text="Led backend team",
            new_text="Led backend team building Kubernetes-native microservices",
        ),
        TailoredItemLLM(
            source_id="master:exp-1-b2", action="keep", original_text="Built microservices"
        ),
        TailoredItemLLM(source_id="master:exp-2-b1", action="drop", original_text="Full-stack"),
        TailoredItemLLM(source_id="master:skill:Python", action="keep", original_text="Python"),
    ],
    notes=["Emphasized backend/microservices, dropped full-stack bullet."],
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


class TestOptimizeContent:
    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    def test_builds_tailored_resume(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(VALID_OUTPUT)

        result = optimize_content(sample_state)

        assert "tailored_resume" in result
        assert len(result["tailored_resume"].items) == 4
        assert result["tailored_resume"].items[0].action == "reword"
        assert "Kubernetes-native" in result["tailored_resume"].items[0].new_text
        # Tailored summary round-trips (issue #66).
        assert result["tailored_resume"].tailored_summary.startswith("Senior engineer")
        # Tailored headline round-trips (issue #70).
        assert result["tailored_resume"].tailored_headline == (
            "Senior Backend Engineer · 8+ years · Python, AWS"
        )
        # Legacy projection still populates sections for back-compat, and the
        # tailored_summary wins over any kept master:summary.
        assert "optimized_resume" in result
        assert result["optimized_resume"].sections["summary"].startswith("Senior engineer")
        assert result["optimized_resume"].sections["experience"].startswith("- ")
        assert result["optimized_resume"].sections["skills"] == "Python"

    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    def test_rejects_fabricated_source_id(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            TailoredResumeLLMOutput(
                items=[
                    TailoredItemLLM(source_id="master:exp-1-b1", action="keep"),
                    # This ID does not exist in the source index — should be rejected.
                    TailoredItemLLM(source_id="master:exp-99-b99", action="keep"),
                ]
            )
        )

        result = optimize_content(sample_state)

        assert len(result["tailored_resume"].items) == 1
        assert any("fabricated source_id" in e for e in result["errors"])

    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    def test_coerces_unknown_action(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            TailoredResumeLLMOutput(
                items=[TailoredItemLLM(source_id="master:exp-1-b1", action="delete")]
            )
        )

        result = optimize_content(sample_state)

        # Unknown action coerced to the safe default "keep".
        assert result["tailored_resume"].items[0].action == "keep"

    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    def test_handles_llm_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API error"))

        result = optimize_content(sample_state)

        assert "errors" in result
        assert any("LLM call failed" in e for e in result["errors"])
        assert "tailored_resume" not in result

    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    def test_handles_schema_validation_error(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        try:
            TailoredResumeLLMOutput.model_validate({"items": "not-a-list"})
        except ValidationError as exc:
            mock_get_llm.return_value = _make_llm(exc)

        result = optimize_content(sample_state)

        assert "errors" in result
        assert any("schema-invalid" in e for e in result["errors"])
        assert "tailored_resume" not in result

    def test_skips_when_master_is_empty(self) -> None:
        state = ResumeOptimizerState()  # empty master + facts
        result = optimize_content(state)

        assert "errors" in result
        assert any("source index is empty" in e for e in result["errors"])


class TestKeptRatioGuard:
    """Post-run guard surfaces a warning when the tailor keeps too much (#76)."""

    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    def test_warns_when_kept_ratio_above_threshold(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        """sample_master has a known number of source_index entries. If the
        LLM 'keeps' almost all of them, the guard should surface a warning
        note in tailored.notes marked with the ⚠ glyph."""
        from lucky_resume.tools.source_index import build_source_index

        # Count how many items the source_index produces for sample_master.
        # We'll keep all of them to force a 100% ratio.
        index = build_source_index(sample_state.master, sample_state.facts)
        all_items = [
            TailoredItemLLM(source_id=sid, action="keep", original_text=entry.text)
            for sid, entry in index.entries.items()
            if not sid.startswith("master:summary")  # summary lives on its own field
        ]

        mock_get_llm.return_value = _make_llm(
            TailoredResumeLLMOutput(
                tailored_headline="x",
                tailored_summary="y",
                items=all_items,
                notes=["LLM-provided strategy note"],
            )
        )

        result = optimize_content(sample_state)
        tailored = result["tailored_resume"]

        # Warning marker (⚠) landed in notes — surfaces in diff.md's Warnings block.
        warning_notes = [n for n in tailored.notes if n.lstrip().startswith("⚠")]
        assert len(warning_notes) == 1
        assert "under-optimizing" in warning_notes[0]
        # Strategy note preserved alongside the warning.
        assert any("LLM-provided" in n for n in tailored.notes)

    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    def test_no_warning_when_kept_ratio_below_threshold(
        self, mock_get_llm: MagicMock, sample_state: ResumeOptimizerState
    ) -> None:
        """A well-tailored run that drops most items shouldn't get the warning."""
        from lucky_resume.tools.source_index import build_source_index

        index = build_source_index(sample_state.master, sample_state.facts)
        all_sids = [sid for sid in index.entries if not sid.startswith("master:summary")]
        # Keep only the first 2 items; drop the rest.
        items = [
            TailoredItemLLM(source_id=all_sids[0], action="keep", original_text=""),
            TailoredItemLLM(source_id=all_sids[1], action="keep", original_text=""),
        ] + [
            TailoredItemLLM(source_id=sid, action="drop", original_text="") for sid in all_sids[2:]
        ]

        mock_get_llm.return_value = _make_llm(
            TailoredResumeLLMOutput(items=items, tailored_headline="", tailored_summary="")
        )

        result = optimize_content(sample_state)
        tailored = result["tailored_resume"]

        warning_notes = [n for n in tailored.notes if n.lstrip().startswith("⚠")]
        assert warning_notes == []
