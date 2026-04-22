"""Tests for `tools.enrich`."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from resume_operator.state import FactItem, FactsBank, ResumeMaster
from resume_operator.tools.enrich import (
    AcceptedItem,
    EnrichQuestionLLM,
    EnrichQuestionsLLMOutput,
    PolishedFactLLMOutput,
    Question,
    SessionPlan,
    assemble_additions,
    collect_existing_ids,
    generate_questions,
    polish_answer,
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


class TestGenerateQuestions:
    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_returns_questions(self, mock_get_llm: MagicMock, sample_master: ResumeMaster) -> None:
        mock_get_llm.return_value = _make_llm(
            EnrichQuestionsLLMOutput(
                questions=[
                    EnrichQuestionLLM(
                        area="role:exp-1",
                        question="At TechCorp, what was the scale of the backend system?",
                        why="The JD emphasizes scalable backend work.",
                    ),
                    EnrichQuestionLLM(
                        area="jd:Docker",
                        question="Did you containerize any service you shipped?",
                        why="JD requires Docker experience.",
                    ),
                ]
            )
        )

        result = generate_questions(
            sample_master, FactsBank(), "Backend role; Docker required.", n_max=5
        )

        assert len(result) == 2
        assert result[0].area == "role:exp-1"
        assert "backend" in result[0].question.lower()
        assert result[1].question.startswith("Did you")

    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_caps_at_n_max(self, mock_get_llm: MagicMock, sample_master: ResumeMaster) -> None:
        mock_get_llm.return_value = _make_llm(
            EnrichQuestionsLLMOutput(
                questions=[EnrichQuestionLLM(question=f"Q{i}?") for i in range(10)]
            )
        )

        result = generate_questions(sample_master, FactsBank(), "JD text", n_max=3)

        assert len(result) == 3

    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_filters_empty_questions(
        self, mock_get_llm: MagicMock, sample_master: ResumeMaster
    ) -> None:
        mock_get_llm.return_value = _make_llm(
            EnrichQuestionsLLMOutput(
                questions=[
                    EnrichQuestionLLM(question="Real question?"),
                    EnrichQuestionLLM(question=""),
                    EnrichQuestionLLM(question="   "),
                ]
            )
        )

        result = generate_questions(sample_master, FactsBank(), "JD", n_max=5)
        assert len(result) == 1

    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_returns_empty_on_llm_error(
        self, mock_get_llm: MagicMock, sample_master: ResumeMaster
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API down"))

        result = generate_questions(sample_master, FactsBank(), "JD", n_max=5)

        assert result == []


class TestPolishAnswer:
    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_returns_polished_bullet(
        self, mock_get_llm: MagicMock, sample_master: ResumeMaster
    ) -> None:
        polished = "Designed RESTful API for 50+ endpoints at TechCorp, cutting p99 latency 30%."
        mock_get_llm.return_value = _make_llm(
            PolishedFactLLMOutput(
                polished_text=polished,
                bucket="extra_bullet",
                role_id="exp-1",
            )
        )
        question = Question(area="role:exp-1", question="q?", why="why")

        result = polish_answer(question, "I designed the REST API", sample_master, "JD")

        assert result is not None
        assert result.bucket == "extra_bullet"
        assert result.role_id == "exp-1"
        assert "RESTful" in result.polished_text

    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_demotes_to_project_when_role_id_unknown(
        self, mock_get_llm: MagicMock, sample_master: ResumeMaster
    ) -> None:
        """If the LLM returns extra_bullet with a role_id that doesn't exist
        on the master, we fall back to `project` to keep the facts_bank sane."""
        mock_get_llm.return_value = _make_llm(
            PolishedFactLLMOutput(
                polished_text="Built a thing.",
                bucket="extra_bullet",
                role_id="exp-999",  # not on master
            )
        )
        question = Question(area="x", question="q?", why="w")

        result = polish_answer(question, "a", sample_master, "JD")

        assert result is not None
        assert result.bucket == "project"
        assert result.role_id == ""

    @patch("resume_operator.tools.enrich.get_structured_llm")
    def test_returns_none_on_llm_error(
        self, mock_get_llm: MagicMock, sample_master: ResumeMaster
    ) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API down"))
        question = Question(area="x", question="q?", why="w")

        result = polish_answer(question, "a", sample_master, "JD")

        assert result is None


class TestAssembleAdditions:
    def test_splits_by_bucket(self) -> None:
        plan = SessionPlan(
            items=[
                AcceptedItem(text="Built a pipeline", bucket="project"),
                AcceptedItem(text="Led team of 4", bucket="extra_bullet", role_id="exp-1"),
                AcceptedItem(text="Terraform", bucket="skill"),
                AcceptedItem(text="AWS Solutions Architect", bucket="certification"),
            ]
        )

        projects, extras, skills, certs = assemble_additions(plan, today=date(2026, 4, 21))

        assert len(projects) == 1
        assert projects[0].text == "Built a pipeline"
        assert projects[0].source == "enrich 2026-04-21"
        assert projects[0].id.startswith("enrich-20260421-")

        assert len(extras) == 1
        assert extras[0].role_id == "exp-1"

        assert skills == ["Terraform"]
        assert certs == ["AWS Solutions Architect"]

    def test_mints_unique_ids_avoiding_collisions(self) -> None:
        plan = SessionPlan(
            items=[
                AcceptedItem(text="First", bucket="project"),
                AcceptedItem(text="Second", bucket="project"),
            ]
        )

        projects, _, _, _ = assemble_additions(
            plan,
            today=date(2026, 4, 21),
            existing_ids={"enrich-20260421-1", "enrich-20260421-2"},
        )

        assert [p.id for p in projects] == ["enrich-20260421-3", "enrich-20260421-4"]

    def test_skips_empty_text(self) -> None:
        plan = SessionPlan(
            items=[
                AcceptedItem(text="   ", bucket="project"),
                AcceptedItem(text="Real one", bucket="project"),
            ]
        )

        projects, _, _, _ = assemble_additions(plan, today=date(2026, 4, 21))

        assert len(projects) == 1
        assert projects[0].text == "Real one"


class TestCollectExistingIds:
    def test_collects_from_both_item_lists(self) -> None:
        bank = FactsBank(
            projects=[FactItem(id="proj-1", text="x")],
            extra_bullets=[FactItem(id="extra-1", text="y", role_id="exp-1")],
        )
        assert collect_existing_ids(bank) == {"proj-1", "extra-1"}


class TestAppendToFacts:
    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        from resume_operator.tools.facts_bank import append_to_facts, load_facts

        out = tmp_path / "facts.yaml"
        append_to_facts(
            out,
            projects=[FactItem(id="p1", text="A thing", source="enrich 2026-04-21")],
        )
        assert out.exists()

        loaded = load_facts(out)
        assert len(loaded.projects) == 1
        assert loaded.projects[0].source == "enrich 2026-04-21"

    def test_preserves_existing_items_and_appends(self, tmp_path: Path) -> None:
        from resume_operator.tools.facts_bank import append_to_facts, load_facts, save_facts

        out = tmp_path / "facts.yaml"
        initial = FactsBank(
            projects=[FactItem(id="old-1", text="existing project")],
            skills_beyond_master=["Docker"],
        )
        save_facts(initial, out)

        append_to_facts(
            out,
            projects=[FactItem(id="new-1", text="new project", source="enrich")],
            skills=["Kubernetes", "Docker"],  # Docker already present — should dedupe
        )

        loaded = load_facts(out)
        assert {p.id for p in loaded.projects} == {"old-1", "new-1"}
        assert loaded.skills_beyond_master == ["Docker", "Kubernetes"]

    def test_id_collision_overrides(self, tmp_path: Path) -> None:
        """Same id → last write wins (caller is responsible for unique IDs)."""
        from resume_operator.tools.facts_bank import append_to_facts, load_facts, save_facts

        out = tmp_path / "facts.yaml"
        save_facts(FactsBank(projects=[FactItem(id="p1", text="old text")]), out)

        append_to_facts(out, projects=[FactItem(id="p1", text="new text")])

        loaded = load_facts(out)
        assert len(loaded.projects) == 1
        assert loaded.projects[0].text == "new text"
