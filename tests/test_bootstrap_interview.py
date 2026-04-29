"""Tests for `tools.bootstrap_interview` + `tools.skill_grouping`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rich.console import Console

from lucky_resume.prompters import RichPrompter
from lucky_resume.state import (
    ExperienceBullet,
    ExperienceEntry,
    Link,
    ResumeMaster,
    SkillGroup,
)
from lucky_resume.tools.bootstrap_interview import (
    run_interview,
    should_run_interview,
)
from lucky_resume.tools.skill_grouping import (
    SkillGroupLLM,
    SkillGroupsLLMOutput,
    propose_groups,
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    llm = MagicMock()
    if isinstance(return_value, Exception):
        llm.invoke.side_effect = return_value
    else:
        llm.invoke.return_value = return_value
    return llm


def _silent_console() -> Console:
    """A Console that doesn't write anywhere — useful in tests."""
    import io

    return Console(file=io.StringIO(), force_terminal=False, record=False)


def _silent_prompter() -> RichPrompter:
    """A `RichPrompter` backed by a silent Console. Still routes prompts
    through `rich.prompt.Prompt.ask` / `Confirm.ask` so tests can patch
    those directly."""
    return RichPrompter(_silent_console())


def _minimal_master() -> ResumeMaster:
    return ResumeMaster(
        name="Jane Smith",
        email="jane@example.com",
        experience=[
            ExperienceEntry(
                id="exp-1",
                role="Senior Engineer",
                company="TechCorp",
                bullets=[ExperienceBullet(id="exp-1-b1", text="Did stuff")],
            )
        ],
        skills=["Python", "AWS", "PostgreSQL", "Docker"],
    )


class TestShouldRunInterview:
    def test_opts_out_when_no_interview_flag(self) -> None:
        assert should_run_interview(no_interview=True) is False

    @patch("sys.stdin.isatty", return_value=True)
    def test_runs_in_tty(self, _tty: MagicMock) -> None:
        assert should_run_interview(no_interview=False) is True

    @patch("sys.stdin.isatty", return_value=False)
    def test_skips_when_no_tty(self, _tty: MagicMock) -> None:
        """Piped stdin (CI, `echo ... | bootstrap`) must never block on prompts."""
        assert should_run_interview(no_interview=False) is False


class TestRunInterviewHeadline:
    def test_fills_empty_headline(self) -> None:
        master = _minimal_master()
        assert master.headline == ""

        # Prompt.ask is called for: headline, 3 links, 1 role tech → 5 calls total.
        # Grouping confirm is a Confirm.ask, separate.
        answers = iter(
            [
                "Senior Engineer · 10+ years · Python",  # headline
                "skip",  # Portfolio
                "skip",  # LinkedIn
                "skip",  # GitHub
                "skip",  # exp-1 tech
            ]
        )
        with (
            patch("rich.prompt.Prompt.ask", side_effect=lambda *a, **kw: next(answers)),
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            run_interview(master, prompter=_silent_prompter())
        assert master.headline == "Senior Engineer · 10+ years · Python"

    def test_skips_when_user_types_skip(self) -> None:
        master = _minimal_master()
        with (
            patch("rich.prompt.Prompt.ask", return_value="skip"),
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            run_interview(master, prompter=_silent_prompter())
        assert master.headline == ""

    def test_existing_headline_not_re_asked(self) -> None:
        master = _minimal_master()
        master.headline = "Pre-existing tagline"
        with (
            patch("rich.prompt.Prompt.ask", return_value="skip"),
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            run_interview(master, prompter=_silent_prompter())
        assert master.headline == "Pre-existing tagline"


class TestRunInterviewLinks:
    def test_prompts_for_each_standard_label_missing(self) -> None:
        """Labels prompted in module-defined order: Portfolio → LinkedIn → GitHub."""
        master = _minimal_master()
        answers = iter(
            [
                "skip",  # headline
                "janesmith.example",  # Portfolio url
                "linkedin.com/in/jane",  # LinkedIn url
                "skip",  # GitHub url
                "skip",  # per-role tech for exp-1
            ]
        )
        with (
            patch("rich.prompt.Prompt.ask", side_effect=lambda *a, **kw: next(answers)),
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            run_interview(master, prompter=_silent_prompter())

        labels = {lk.label for lk in master.links}
        assert labels == {"Portfolio", "LinkedIn"}

    def test_does_not_re_ask_for_existing_label(self) -> None:
        master = _minimal_master()
        master.links = [Link(label="GitHub", url="github.com/jsmith")]
        # Only 2 labels missing (Portfolio, LinkedIn). Answer: skip everything.
        with (
            patch("rich.prompt.Prompt.ask", return_value="skip"),
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            run_interview(master, prompter=_silent_prompter())
        # Still just the one pre-existing link.
        assert len(master.links) == 1
        assert master.links[0].label == "GitHub"


class TestRunInterviewPerRoleTech:
    def test_fills_tech_for_roles_missing_it(self) -> None:
        master = _minimal_master()
        master.experience.append(
            ExperienceEntry(
                id="exp-2",
                role="Junior Engineer",
                company="Widget",
                bullets=[ExperienceBullet(id="exp-2-b1", text="Built stuff")],
                tech=["JavaScript"],  # already populated — should be skipped
            )
        )

        answers = iter(
            [
                "skip",  # headline
                "skip",  # Portfolio
                "skip",  # LinkedIn
                "skip",  # GitHub
                "Python, PostgreSQL, Docker",  # exp-1 tech (exp-2 has tech already)
            ]
        )
        with (
            patch("rich.prompt.Prompt.ask", side_effect=lambda *a, **kw: next(answers)),
            patch("rich.prompt.Confirm.ask", return_value=False),
        ):
            run_interview(master, prompter=_silent_prompter())

        assert master.experience[0].tech == ["Python", "PostgreSQL", "Docker"]
        # exp-2's tech is untouched.
        assert master.experience[1].tech == ["JavaScript"]


class TestRunInterviewSkillGrouping:
    @patch("lucky_resume.tools.bootstrap_interview.propose_groups")
    def test_asks_confirmation_and_writes_groups_on_accept(self, mock_propose: MagicMock) -> None:
        master = _minimal_master()
        mock_propose.return_value = [
            SkillGroup(category="Languages", items=["Python"]),
            SkillGroup(category="Cloud", items=["AWS", "Docker"]),
            SkillGroup(category="Data", items=["PostgreSQL"]),
        ]

        answers = iter(
            [
                "skip",  # headline
                "skip",  # Portfolio
                "skip",  # LinkedIn
                "skip",  # GitHub
                "skip",  # exp-1 tech
                "a",  # accept grouping
            ]
        )
        with (
            patch("rich.prompt.Prompt.ask", side_effect=lambda *a, **kw: next(answers)),
            patch("rich.prompt.Confirm.ask", return_value=True),
        ):
            run_interview(master, prompter=_silent_prompter())

        assert len(master.skill_groups) == 3
        categories = {g.category for g in master.skill_groups}
        assert categories == {"Languages", "Cloud", "Data"}

    @patch("lucky_resume.tools.bootstrap_interview.propose_groups")
    def test_reject_leaves_groups_empty(self, mock_propose: MagicMock) -> None:
        master = _minimal_master()
        mock_propose.return_value = [
            SkillGroup(category="Everything", items=["Python", "AWS", "PostgreSQL", "Docker"])
        ]

        answers = iter(
            ["skip", "skip", "skip", "skip", "skip", "r"]  # reject grouping
        )
        with (
            patch("rich.prompt.Prompt.ask", side_effect=lambda *a, **kw: next(answers)),
            patch("rich.prompt.Confirm.ask", return_value=True),
        ):
            run_interview(master, prompter=_silent_prompter())

        assert master.skill_groups == []

    @patch("lucky_resume.tools.bootstrap_interview.propose_groups")
    def test_skipped_when_user_says_no(self, mock_propose: MagicMock) -> None:
        master = _minimal_master()

        with (
            patch("rich.prompt.Prompt.ask", return_value="skip"),
            patch("rich.prompt.Confirm.ask", return_value=False),  # declines grouping
        ):
            run_interview(master, prompter=_silent_prompter())

        mock_propose.assert_not_called()
        assert master.skill_groups == []

    @patch("lucky_resume.tools.bootstrap_interview.propose_groups")
    def test_skipped_when_skills_too_few(self, mock_propose: MagicMock) -> None:
        master = _minimal_master()
        master.skills = ["Python"]  # below the min-3 threshold

        with (
            patch("rich.prompt.Prompt.ask", return_value="skip"),
            patch("rich.prompt.Confirm.ask", return_value=True),
        ):
            run_interview(master, prompter=_silent_prompter())

        mock_propose.assert_not_called()
        assert master.skill_groups == []


class TestProposeGroups:
    @patch("lucky_resume.tools.skill_grouping.get_structured_llm")
    def test_returns_groups_with_canonicalised_casing(self, mock_get_llm: MagicMock) -> None:
        # Input skills have "Python" (capital P); LLM returns "python" (lower).
        # propose_groups should match case-insensitively and keep the original.
        mock_get_llm.return_value = _make_llm(
            SkillGroupsLLMOutput(
                groups=[
                    SkillGroupLLM(category="Languages", items=["python"]),
                    SkillGroupLLM(category="Cloud", items=["AWS", "Docker"]),
                ]
            )
        )
        result = propose_groups(["Python", "AWS", "Docker"])

        assert [g.category for g in result] == ["Languages", "Cloud"]
        # Python preserved with its original casing.
        assert "Python" in result[0].items

    @patch("lucky_resume.tools.skill_grouping.get_structured_llm")
    def test_rejects_fabricated_skills(self, mock_get_llm: MagicMock) -> None:
        """If the LLM invents a skill that wasn't in the input, it gets filtered out."""
        mock_get_llm.return_value = _make_llm(
            SkillGroupsLLMOutput(
                groups=[
                    SkillGroupLLM(category="Languages", items=["Python", "Kotlin"]),
                ]
            )
        )
        result = propose_groups(["Python"])  # Kotlin not in input

        items = [item for g in result for item in g.items]
        assert "Python" in items
        assert "Kotlin" not in items

    @patch("lucky_resume.tools.skill_grouping.get_structured_llm")
    def test_collects_ungrouped_skills_into_other(self, mock_get_llm: MagicMock) -> None:
        """Input skills the LLM didn't place end up in an 'Other' group so they're
        not silently lost."""
        mock_get_llm.return_value = _make_llm(
            SkillGroupsLLMOutput(groups=[SkillGroupLLM(category="Languages", items=["Python"])])
        )
        result = propose_groups(["Python", "AWS", "Docker"])

        categories = {g.category: g.items for g in result}
        assert "Languages" in categories
        assert "Other" in categories
        assert sorted(categories["Other"]) == ["AWS", "Docker"]

    @patch("lucky_resume.tools.skill_grouping.get_structured_llm")
    def test_returns_empty_on_llm_failure(self, mock_get_llm: MagicMock) -> None:
        mock_get_llm.return_value = _make_llm(RuntimeError("API down"))
        assert propose_groups(["Python"]) == []

    def test_empty_input_returns_empty(self) -> None:
        assert propose_groups([]) == []
