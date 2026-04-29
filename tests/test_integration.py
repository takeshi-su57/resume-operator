"""Full pipeline integration test with mocked LLM and I/O.

Runs the complete LangGraph pipeline from parse_resume through report_results,
verifying state flows correctly through all six nodes and edges work end-to-end.
All external I/O (LLM calls, PDF parsing, PDF generation, file writes) is mocked.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from lucky_resume.graph import build_graph
from lucky_resume.nodes.analyze_gaps import GapAnalysisLLMOutput
from lucky_resume.nodes.optimize_content import TailoredItemLLM, TailoredResumeLLMOutput
from lucky_resume.nodes.parse_resume import (
    ResumeEducationLLM,
    ResumeExperienceLLM,
    ResumeLLMOutput,
)
from lucky_resume.state import SkillCountRow

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

# #81: the ATS orchestrator no longer uses a single LLM call — it calls
# `extract_keywords` and `check_tone` as separate tools. Integration tests
# mock those directly; the deterministic structural checks run for real.
ATS_HARD_SKILLS = [
    SkillCountRow(name="Python", resume_count=2, jd_count=2),
    SkillCountRow(name="AWS", resume_count=2, jd_count=1),
    SkillCountRow(name="Kubernetes", resume_count=0, jd_count=3),
    SkillCountRow(name="CI/CD", resume_count=0, jd_count=1),
]
ATS_SOFT_SKILLS: list[SkillCountRow] = []

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
    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    @patch("lucky_resume.nodes.analyze_gaps.get_structured_llm")
    @patch("lucky_resume.nodes.ats_score.check_tone")
    @patch("lucky_resume.nodes.ats_score.extract_keywords")
    @patch("lucky_resume.nodes.parse_resume.get_structured_llm")
    @patch("lucky_resume.nodes.parse_resume.extract_text")
    def test_full_pipeline_happy_path(
        self,
        mock_extract: MagicMock,
        mock_parse_llm: MagicMock,
        mock_ats_keywords: MagicMock,
        mock_ats_tone: MagicMock,
        mock_gaps_llm: MagicMock,
        mock_optimize_llm: MagicMock,
        mock_create_pdf: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_extract.return_value = "Jane Smith\njane@example.com\nSenior Python engineer"
        mock_parse_llm.return_value = _make_llm(PARSED_RESUME)
        mock_ats_keywords.return_value = (ATS_HARD_SKILLS, ATS_SOFT_SKILLS)
        mock_ats_tone.return_value = []
        mock_gaps_llm.return_value = _make_llm(GAPS_OUT)
        mock_optimize_llm.return_value = _make_llm(OPTIMIZED_OUT)
        mock_create_pdf.return_value = _make_mock_pdf_path("output/resume.pdf")

        results_file = tmp_path / "data" / "results.json"
        with patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file):
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

        # Composite score is in bounds; derived keyword_matches / keyword_gaps
        # come from the mocked extractor output.
        assert 0.0 <= result["ats_score"].score <= 1.0
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

    @patch("lucky_resume.nodes.generate_pdf.create_pdf")
    @patch("lucky_resume.nodes.optimize_content.get_structured_llm")
    @patch("lucky_resume.nodes.analyze_gaps.get_structured_llm")
    @patch("lucky_resume.nodes.ats_score.check_tone")
    @patch("lucky_resume.nodes.ats_score.extract_keywords")
    @patch("lucky_resume.nodes.parse_resume.get_structured_llm")
    @patch("lucky_resume.nodes.parse_resume.extract_text")
    def test_pipeline_continues_on_llm_pass_failure(
        self,
        mock_extract: MagicMock,
        mock_parse_llm: MagicMock,
        mock_ats_keywords: MagicMock,
        mock_ats_tone: MagicMock,
        mock_gaps_llm: MagicMock,
        mock_optimize_llm: MagicMock,
        mock_create_pdf: MagicMock,
        tmp_path: Path,
    ) -> None:
        """#81: the ATS orchestrator no longer fails the pipeline when an LLM
        sub-pass fails — it absorbs the failure (empty tables / flags) and the
        composite score is derived from the structural half alone.
        """
        mock_extract.return_value = "Jane Smith\njane@example.com"
        mock_parse_llm.return_value = _make_llm(PARSED_RESUME)
        # Both LLM passes return empty (what the tools return on failure).
        mock_ats_keywords.return_value = ([], [])
        mock_ats_tone.return_value = []
        mock_gaps_llm.return_value = _make_llm(GAPS_OUT)
        mock_optimize_llm.return_value = _make_llm(OPTIMIZED_OUT)
        mock_create_pdf.return_value = _make_mock_pdf_path()

        results_file = tmp_path / "data" / "results.json"
        with patch("lucky_resume.nodes.report_results.RESULTS_PATH", results_file):
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
        # Pipeline kept running; ats_score produced a valid (degraded) report.
        assert "ats_score" in result
        assert 0.0 <= result["ats_score"].score <= 1.0
        assert result["ats_score"].hard_skills == []
        assert len(result["gap_analysis"].gaps) > 0
        assert result["tailored_resume"].items
        assert isinstance(result["report"], dict)
