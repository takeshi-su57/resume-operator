"""Tests for LangGraph graph assembly and execution.

LangGraph Concepts:
- StateGraph(Type): Creates a graph parameterized by a state type (here, Pydantic BaseModel).
- graph.add_node("name", fn): Registers a node function that receives state and returns a dict.
- graph.add_edge(START, "name"): Defines execution flow between nodes.
- graph.compile(): Produces a CompiledStateGraph — a runnable that accepts initial state.
- compiled.invoke(state): Executes the full pipeline; each node's return dict is merged into state.
- Stub nodes returning {} are valid — they simply don't modify state, so the pipeline continues.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from langgraph.graph.state import CompiledStateGraph

from lucky_resume.graph import _route_after_ats_score, build_graph
from lucky_resume.nodes.parse_resume import ResumeLLMOutput
from lucky_resume.state import (
    ATSReport,
    ContactCheck,
    ResumeOptimizerState,
    SectionCheck,
    SkillCountRow,
)


def _healthy_report(score: float) -> ATSReport:
    """Skip-eligible report: high composite + LLM data + good structural signal.
    Used by the routing tests that want to exercise the skip path."""
    return ATSReport(
        score=score,
        contact=ContactCheck(email_present=True, phone_present=True, address_present=True),
        sections=SectionCheck(summary=True, experience=True, education=True, skills=True),
        word_count=700,
        word_count_ok=True,
        hard_skills=[
            SkillCountRow(name="Python", resume_count=2, jd_count=1),
            SkillCountRow(name="AWS", resume_count=2, jd_count=1),
            SkillCountRow(name="Docker", resume_count=1, jd_count=1),
        ],
    )


EXPECTED_NODES = [
    "load_master",
    "parse_resume",
    "ats_score",
    "analyze_gaps",
    "optimize_content",
    "generate_pdf",
    "report_results",
]

PARSED = ResumeLLMOutput(
    name="Jane Smith",
    email="jane@example.com",
    summary="Engineer",
    skills=["Python"],
)


class TestGraphAssembly:
    def test_graph_compiles(self) -> None:
        """build_graph() returns a compiled graph with all expected nodes."""
        # compile() converts the StateGraph into a runnable — no nodes execute yet
        graph = build_graph()

        assert isinstance(graph, CompiledStateGraph)

        # __start__ and __end__ are LangGraph internal nodes; filter to user-defined nodes
        node_names = [n for n in graph.get_graph().nodes if not n.startswith("__")]
        assert sorted(node_names) == sorted(EXPECTED_NODES)

    @patch("lucky_resume.nodes.report_results.RESULTS_PATH")
    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    @patch("lucky_resume.nodes.analyze_gaps.get_structured_llm")
    @patch("lucky_resume.nodes.ats_score.check_tone")
    @patch("lucky_resume.nodes.ats_score.extract_keywords")
    @patch("lucky_resume.nodes.parse_resume.get_structured_llm")
    @patch("lucky_resume.nodes.parse_resume.extract_text")
    def test_graph_runs_parse_resume(
        self,
        mock_extract: MagicMock,
        mock_parse_llm: MagicMock,
        mock_ats_keywords: MagicMock,
        mock_ats_tone: MagicMock,
        mock_gaps_llm: MagicMock,
        mock_optimize_llm: MagicMock,
        mock_create_pdf: MagicMock,
        mock_results_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Invoking the graph executes parse_resume and merges its output into state."""
        mock_extract.return_value = "Jane Smith\njane@example.com"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = PARSED
        mock_parse_llm.return_value = mock_llm

        # Other LLM-calling nodes: let them fail or no-op gracefully
        mock_ats_keywords.return_value = ([], [])
        mock_ats_tone.return_value = []
        mock_gaps_llm.side_effect = RuntimeError("not under test")
        mock_optimize_llm.side_effect = RuntimeError("not under test")

        results_file = tmp_path / "data" / "results.json"
        with patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file):
            graph = build_graph()

            result = graph.invoke(
                {
                    "resume_path": "test.pdf",
                    "job_description_text": "Backend Engineer role",
                }
            )

        # parse_resume was called — verify via mock
        mock_extract.assert_called_once()
        mock_parse_llm.assert_called_once()

        # State merging: parse_resume returned {"resume": ResumeData, "job_description": ...}
        # LangGraph merged those into the pipeline state dict
        assert "resume" in result
        assert result["resume"].name == "Jane Smith"
        assert result["resume"].skills == ["Python"]

        assert "job_description" in result
        assert result["job_description"].raw_text == "Backend Engineer role"


class TestConditionalRouting:
    @patch("lucky_resume.graph.get_settings")
    def test_high_score_with_healthy_subdimensions_skips(self, mock_settings: MagicMock) -> None:
        """Composite ≥ threshold AND hard coverage + structural healthy → skip."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState(ats_score=_healthy_report(0.95))
        assert _route_after_ats_score(state) == "skip"

    @patch("lucky_resume.graph.get_settings")
    def test_threshold_score_with_healthy_subdimensions_skips(
        self, mock_settings: MagicMock
    ) -> None:
        """Composite exactly at threshold still skips if sub-dimensions healthy."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState(ats_score=_healthy_report(0.9))
        assert _route_after_ats_score(state) == "skip"

    @patch("lucky_resume.graph.get_settings")
    def test_low_score_routes_to_optimize(self, mock_settings: MagicMock) -> None:
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState(ats_score=ATSReport(score=0.72))
        assert _route_after_ats_score(state) == "optimize"

    @patch("lucky_resume.graph.get_settings")
    def test_high_score_but_no_llm_data_still_optimizes(self, mock_settings: MagicMock) -> None:
        """#81 regression guard: pre-#81, a garbage LLM returning score=1.0
        with empty keyword data falsely skipped optimization. The hardened
        gate requires LLM keyword data to trust the composite."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState(
            ats_score=ATSReport(score=0.98, hard_skills=[], soft_skills=[])
        )
        assert _route_after_ats_score(state) == "optimize"

    @patch("lucky_resume.graph.get_settings")
    def test_high_score_but_low_hard_coverage_still_optimizes(
        self, mock_settings: MagicMock
    ) -> None:
        """Even with LLM data, if hard-skill coverage is weak the composite
        is misleading — keep optimizing."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState(
            ats_score=ATSReport(
                score=0.95,
                hard_skills=[
                    SkillCountRow(name="Python", resume_count=0, jd_count=1),
                    SkillCountRow(name="K8s", resume_count=0, jd_count=1),
                    SkillCountRow(name="AWS", resume_count=1, jd_count=1),
                ],  # 1/3 coverage = 0.33, below the 0.7 minimum
                contact=ContactCheck(email_present=True, phone_present=True),
                sections=SectionCheck(summary=True, experience=True, education=True, skills=True),
                word_count_ok=True,
            )
        )
        assert _route_after_ats_score(state) == "optimize"

    @patch("lucky_resume.graph.get_settings")
    def test_zero_score_routes_to_optimize(self, mock_settings: MagicMock) -> None:
        """Default zero score routes to 'optimize'."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState()

        assert _route_after_ats_score(state) == "optimize"
