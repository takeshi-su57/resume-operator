"""Full pipeline integration test with mocked LLM and I/O.

Runs the complete LangGraph pipeline from parse_resume through report_results,
verifying state flows correctly through all six nodes and edges work end-to-end.
All external I/O (LLM calls, PDF parsing, PDF generation, file writes) is mocked.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from resume_operator.graph import build_graph
from resume_operator.nodes.analyze_gaps import GapAnalysisLLMOutput
from resume_operator.nodes.ats_score import ATSScoreLLMOutput
from resume_operator.nodes.optimize_content import TailoredItemLLM, TailoredResumeLLMOutput
from resume_operator.nodes.parse_resume import (
    ResumeEducationLLM,
    ResumeExperienceLLM,
    ResumeLLMOutput,
)

PARSED_RESUME = ResumeLLMOutput(
    name="Jane Smith",
    email="jane@example.com",
    phone="555-0100",
    summary="Senior Python engineer",
    experience=[
        ResumeExperienceLLM(
            role="Engineer",
            company="Corp",
            start_date="2020",
            end_date="present",
            bullets=["Built APIs", "Shipped to AWS"],
        )
    ],
    education=[ResumeEducationLLM(degree="BS CS", school="State U", end_date="2016")],
    skills=["Python", "AWS", "Docker"],
    certifications=["AWS SA"],
)

ATS_SCORE_OUT = ATSScoreLLMOutput(
    score=0.85,
    reasoning="Strong Python and AWS match",
    keyword_matches=["Python", "AWS"],
    keyword_gaps=["Kubernetes", "CI/CD"],
)

GAPS_OUT = GapAnalysisLLMOutput(
    gaps=["No Kubernetes experience", "No CI/CD mentioned"],
    strengths=["Strong Python background", "AWS certified"],
    suggestions=["Add K8s projects", "Mention CI/CD pipelines"],
)

OPTIMIZED_OUT = TailoredResumeLLMOutput(
    items=[
        TailoredItemLLM(source_id="master:summary", action="keep"),
        TailoredItemLLM(source_id="master:exp-1-b1", action="keep"),
        TailoredItemLLM(source_id="master:skill:Python", action="keep"),
        TailoredItemLLM(source_id="master:skill:AWS", action="keep"),
    ],
    notes=["Emphasized Python and AWS for the backend role."],
)


def _make_llm(return_value: object | Exception) -> MagicMock:
    mock_llm = MagicMock()
    if isinstance(return_value, Exception):
        mock_llm.invoke.side_effect = return_value
    else:
        mock_llm.invoke.return_value = return_value
    return mock_llm


def _make_mock_pdf_path(path_str: str = "data/optimized_resume.pdf") -> MagicMock:
    mock_path = MagicMock(spec=Path)
    mock_path.stat.return_value.st_size = 10000
    mock_path.__str__ = lambda self: path_str
    return mock_path


class TestFullPipeline:
    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    @patch("resume_operator.nodes.analyze_gaps.get_structured_llm")
    @patch("resume_operator.nodes.ats_score.get_structured_llm")
    @patch("resume_operator.nodes.parse_resume.get_structured_llm")
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
        mock_extract.return_value = "Jane Smith\njane@example.com\nSenior Python engineer"
        mock_parse_llm.return_value = _make_llm(PARSED_RESUME)
        mock_ats_llm.return_value = _make_llm(ATS_SCORE_OUT)
        mock_gaps_llm.return_value = _make_llm(GAPS_OUT)
        mock_optimize_llm.return_value = _make_llm(OPTIMIZED_OUT)
        mock_create_pdf.return_value = _make_mock_pdf_path("output/resume.pdf")

        results_file = tmp_path / "data" / "results.json"
        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
            graph = build_graph()
            result = graph.invoke(
                {
                    "resume_path": "test.pdf",
                    "job_description_text": "Backend Engineer needing Python, AWS, Kubernetes",
                    "output_path": "output/resume.pdf",
                }
            )

        assert result["resume"].name == "Jane Smith"
        assert result["resume"].skills == ["Python", "AWS", "Docker"]

        assert result["ats_score"].score == 0.85
        assert "Python" in result["ats_score"].keyword_matches
        assert "Kubernetes" in result["ats_score"].keyword_gaps

        assert len(result["gap_analysis"].gaps) == 2
        assert len(result["gap_analysis"].strengths) == 2
        assert len(result["gap_analysis"].suggestions) == 2

        # Item-level tailored output is the new source of truth.
        assert len(result["tailored_resume"].items) == 4
        assert result["tailored_resume"].notes

        assert result["output_path"] == "output/resume.pdf"
        assert isinstance(result["report"], dict)
        assert "timestamp" in result["report"]
        assert "ats_score" in result["report"]
        assert result.get("errors", []) == []

        mock_extract.assert_called_once()
        mock_create_pdf.assert_called_once()

    @patch("resume_operator.nodes.generate_pdf.create_pdf")
    @patch("resume_operator.nodes.optimize_content.get_structured_llm")
    @patch("resume_operator.nodes.analyze_gaps.get_structured_llm")
    @patch("resume_operator.nodes.ats_score.get_structured_llm")
    @patch("resume_operator.nodes.parse_resume.get_structured_llm")
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
        mock_extract.return_value = "Jane Smith\njane@example.com"
        mock_parse_llm.return_value = _make_llm(PARSED_RESUME)
        mock_ats_llm.return_value = _make_llm(RuntimeError("API unavailable"))
        mock_gaps_llm.return_value = _make_llm(GAPS_OUT)
        mock_optimize_llm.return_value = _make_llm(OPTIMIZED_OUT)
        mock_create_pdf.return_value = _make_mock_pdf_path()

        results_file = tmp_path / "data" / "results.json"
        with patch("resume_operator.nodes.report_results.RESULTS_PATH", results_file):
            graph = build_graph()
            result = graph.invoke(
                {
                    "resume_path": "test.pdf",
                    "job_description_text": "Backend Engineer role",
                    "output_path": "out.pdf",
                }
            )

        assert "resume" in result
        assert result["resume"].name == "Jane Smith"
        assert len(result["errors"]) > 0
        assert any("ats_score" in e for e in result["errors"])
        assert len(result["gap_analysis"].gaps) > 0
        assert result["tailored_resume"].items
        assert isinstance(result["report"], dict)
