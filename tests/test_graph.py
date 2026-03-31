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

from resume_operator.graph import _route_after_ats_score, build_graph
from resume_operator.state import ATSScore, ResumeOptimizerState

EXPECTED_NODES = [
    "parse_resume",
    "ats_score",
    "analyze_gaps",
    "optimize_content",
    "generate_pdf",
    "report_results",
]

VALID_LLM_JSON = """{
    "name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "",
    "summary": "Engineer",
    "experience": [],
    "education": [],
    "skills": ["Python"],
    "certifications": []
}"""


class TestGraphAssembly:
    def test_graph_compiles(self) -> None:
        """build_graph() returns a compiled graph with all expected nodes."""
        # compile() converts the StateGraph into a runnable — no nodes execute yet
        graph = build_graph()

        assert isinstance(graph, CompiledStateGraph)

        # __start__ and __end__ are LangGraph internal nodes; filter to user-defined nodes
        node_names = [n for n in graph.get_graph().nodes if not n.startswith("__")]
        assert sorted(node_names) == sorted(EXPECTED_NODES)

    @patch("resume_operator.nodes.report_results.RESULTS_PATH")
    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    @patch("resume_operator.nodes.optimize_content.get_llm")
    @patch("resume_operator.nodes.analyze_gaps.get_llm")
    @patch("resume_operator.nodes.ats_score.get_llm")
    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_graph_runs_parse_resume(
        self,
        mock_extract: MagicMock,
        mock_parse_llm: MagicMock,
        mock_ats_llm: MagicMock,
        mock_gaps_llm: MagicMock,
        mock_optimize_llm: MagicMock,
        mock_create_pdf: MagicMock,
        mock_results_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Invoking the graph executes parse_resume and merges its output into state."""
        mock_extract.return_value = "Jane Smith\njane@example.com"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = VALID_LLM_JSON
        mock_parse_llm.return_value = mock_llm

        # Other LLM-calling nodes: let them fail gracefully
        mock_ats_llm.side_effect = RuntimeError("not under test")
        mock_gaps_llm.side_effect = RuntimeError("not under test")
        mock_optimize_llm.side_effect = RuntimeError("not under test")

        results_file = tmp_path / "data" / "results.json"
        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
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
    @patch("resume_operator.graph.get_settings")
    def test_high_score_routes_to_skip(self, mock_settings: MagicMock) -> None:
        """ATS score at or above threshold routes to 'skip'."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState(ats_score=ATSScore(score=0.95))

        assert _route_after_ats_score(state) == "skip"

    @patch("resume_operator.graph.get_settings")
    def test_threshold_score_routes_to_skip(self, mock_settings: MagicMock) -> None:
        """ATS score exactly at threshold routes to 'skip'."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState(ats_score=ATSScore(score=0.9))

        assert _route_after_ats_score(state) == "skip"

    @patch("resume_operator.graph.get_settings")
    def test_low_score_routes_to_optimize(self, mock_settings: MagicMock) -> None:
        """ATS score below threshold routes to 'optimize'."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState(ats_score=ATSScore(score=0.72))

        assert _route_after_ats_score(state) == "optimize"

    @patch("resume_operator.graph.get_settings")
    def test_zero_score_routes_to_optimize(self, mock_settings: MagicMock) -> None:
        """Default zero score routes to 'optimize'."""
        mock_settings.return_value.ats_skip_threshold = 0.9
        state = ResumeOptimizerState()

        assert _route_after_ats_score(state) == "optimize"
