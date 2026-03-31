"""Full pipeline integration test with mocked LLM and I/O.

Runs the complete LangGraph pipeline from parse_resume through report_results,
verifying state flows correctly through all six nodes and edges work end-to-end.
All external I/O (LLM calls, PDF parsing, PDF generation, file writes) is mocked.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from resume_operator.graph import build_graph

# --- Canned LLM JSON responses for each node ---

PARSE_RESUME_JSON = """{
    "name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "555-0100",
    "summary": "Senior Python engineer",
    "experience": [
        {"title": "Engineer", "company": "Corp", "dates": "2020-now", "description": "Built APIs"}
    ],
    "education": [{"degree": "BS CS", "institution": "State U", "dates": "2016"}],
    "skills": ["Python", "AWS", "Docker"],
    "certifications": ["AWS SA"]
}"""

ATS_SCORE_JSON = """{
    "score": 0.85,
    "reasoning": "Strong Python and AWS match",
    "keyword_matches": ["Python", "AWS"],
    "keyword_gaps": ["Kubernetes", "CI/CD"]
}"""

ANALYZE_GAPS_JSON = """{
    "gaps": ["No Kubernetes experience", "No CI/CD mentioned"],
    "strengths": ["Strong Python background", "AWS certified"],
    "suggestions": ["Add K8s projects", "Mention CI/CD pipelines"]
}"""

OPTIMIZE_CONTENT_JSON = """{
    "sections": {
        "summary": "Senior Python engineer with cloud and container expertise",
        "experience": "Built APIs and CI/CD pipelines at Corp",
        "skills": "Python, AWS, Docker, Kubernetes, CI/CD",
        "education": "BS CS, State U, 2016"
    },
    "changes_made": ["Added Kubernetes to skills", "Mentioned CI/CD in experience"]
}"""


def _make_mock_llm(response_json: str) -> MagicMock:
    """Create a mock LLM that returns the given JSON from invoke()."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = response_json
    return mock_llm


def _make_mock_pdf_path(path_str: str = "data/optimized_resume.pdf") -> MagicMock:
    """Create a mock Path return value for pdf_generator."""
    mock_path = MagicMock(spec=Path)
    mock_path.stat.return_value.st_size = 10000
    mock_path.__str__ = lambda self: path_str
    return mock_path


class TestFullPipeline:
    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    @patch("resume_operator.nodes.optimize_content.get_llm")
    @patch("resume_operator.nodes.analyze_gaps.get_llm")
    @patch("resume_operator.nodes.ats_score.get_llm")
    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_full_pipeline_happy_path(
        self,
        mock_extract: MagicMock,
        mock_parse_llm: MagicMock,
        mock_ats_llm: MagicMock,
        mock_gaps_llm: MagicMock,
        mock_optimize_llm: MagicMock,
        mock_create_pdf: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full pipeline runs with all state fields populated and no errors."""
        # Arrange: mock PDF extraction
        mock_extract.return_value = "Jane Smith\njane@example.com\nSenior Python engineer"

        # Arrange: each node gets its own mock LLM with canned response
        mock_parse_llm.return_value = _make_mock_llm(PARSE_RESUME_JSON)
        mock_ats_llm.return_value = _make_mock_llm(ATS_SCORE_JSON)
        mock_gaps_llm.return_value = _make_mock_llm(ANALYZE_GAPS_JSON)
        mock_optimize_llm.return_value = _make_mock_llm(OPTIMIZE_CONTENT_JSON)

        # Arrange: mock PDF generation
        mock_create_pdf.return_value = _make_mock_pdf_path("output/resume.pdf")

        # Arrange: redirect report JSON to tmp_path
        results_file = tmp_path / "data" / "results.json"
        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
            # Act
            graph = build_graph()
            result = graph.invoke(
                {
                    "resume_path": "test.pdf",
                    "job_description_text": "Backend Engineer needing Python, AWS, Kubernetes",
                    "output_path": "output/resume.pdf",
                }
            )

        # Assert: all state fields populated
        assert result["resume"].name == "Jane Smith"
        assert result["resume"].skills == ["Python", "AWS", "Docker"]

        assert result["ats_score"].score == 0.85
        assert "Python" in result["ats_score"].keyword_matches
        assert "Kubernetes" in result["ats_score"].keyword_gaps

        assert len(result["gap_analysis"].gaps) == 2
        assert len(result["gap_analysis"].strengths) == 2
        assert len(result["gap_analysis"].suggestions) == 2

        assert "summary" in result["optimized_resume"].sections
        assert len(result["optimized_resume"].changes_made) == 2

        assert result["output_path"] == "output/resume.pdf"

        assert isinstance(result["report"], dict)
        assert "timestamp" in result["report"]
        assert "ats_score" in result["report"]

        assert result.get("errors", []) == []

        # Assert: all mocks were called
        mock_extract.assert_called_once()
        mock_create_pdf.assert_called_once()

    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    @patch("resume_operator.nodes.optimize_content.get_llm")
    @patch("resume_operator.nodes.analyze_gaps.get_llm")
    @patch("resume_operator.nodes.ats_score.get_llm")
    @patch("resume_operator.nodes.parse_resume.get_llm")
    @patch("resume_operator.nodes.parse_resume.extract_text")
    def test_pipeline_continues_on_node_error(
        self,
        mock_extract: MagicMock,
        mock_parse_llm: MagicMock,
        mock_ats_llm: MagicMock,
        mock_gaps_llm: MagicMock,
        mock_optimize_llm: MagicMock,
        mock_create_pdf: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pipeline completes even when a node fails, with errors recorded."""
        # Arrange: parse_resume works
        mock_extract.return_value = "Jane Smith\njane@example.com"
        mock_parse_llm.return_value = _make_mock_llm(PARSE_RESUME_JSON)

        # Arrange: ats_score FAILS
        mock_ats_llm.side_effect = RuntimeError("API unavailable")

        # Arrange: remaining nodes work (they'll use default/empty ats_score)
        mock_gaps_llm.return_value = _make_mock_llm(ANALYZE_GAPS_JSON)
        mock_optimize_llm.return_value = _make_mock_llm(OPTIMIZE_CONTENT_JSON)
        mock_create_pdf.return_value = _make_mock_pdf_path()

        results_file = tmp_path / "data" / "results.json"
        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
            # Act
            graph = build_graph()
            result = graph.invoke(
                {
                    "resume_path": "test.pdf",
                    "job_description_text": "Backend Engineer role",
                    "output_path": "out.pdf",
                }
            )

        # Assert: pipeline completed (not crashed)
        assert "resume" in result
        assert result["resume"].name == "Jane Smith"

        # Assert: error was recorded from ats_score failure
        assert len(result["errors"]) > 0
        assert any("ats_score" in e for e in result["errors"])

        # Assert: downstream nodes still ran
        assert len(result["gap_analysis"].gaps) > 0
        assert len(result["optimized_resume"].sections) > 0
        assert isinstance(result["report"], dict)
