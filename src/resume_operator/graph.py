"""LangGraph StateGraph assembly for the resume optimization pipeline.

Three graphs coexist:

  - `build_graph()` — the original single-pass pipeline
    (load → ats_score → analyze_gaps → optimize_content → generate_pdf →
    report_results). Still used by `parse-resume` and the `--no-approve`
    headless path.

  - `build_tailor_graph()` (#78) — the tailor-only loop body the iterative
    approval CLI invokes repeatedly. Stops at `ats_score_tailored`; the
    CLI drives proposal generation / user approval / re-loop outside the
    graph.

  - `build_finalize_graph()` (#78) — `generate_pdf → report_results`, run
    once by the CLI after the loop exits. Splitting this off avoids
    re-rendering the PDF on every iteration.

  - `build_score_graph()` — score-only path, used by the `score` CLI.
"""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from resume_operator.config import get_settings
from resume_operator.nodes.analyze_gaps import analyze_gaps
from resume_operator.nodes.ats_score import ats_score, ats_score_tailored
from resume_operator.nodes.generate_pdf import generate_pdf
from resume_operator.nodes.load_master import load_master_node
from resume_operator.nodes.optimize_content import optimize_content
from resume_operator.nodes.parse_resume import parse_resume
from resume_operator.nodes.report_results import report_results
from resume_operator.state import ATSReport, ResumeOptimizerState, SkillCountRow

logger = logging.getLogger(__name__)


def _route_after_ats_score(state: ResumeOptimizerState) -> str:
    """Route based on ATS score: skip optimization if composite is high AND
    every critical sub-dimension is healthy (#81).

    Critical dimensions:
      - hard-skill coverage ≥ 0.7 — the JD's technical asks are mostly present
      - at least some keyword data from the LLM extractor — protects against
        the "garbage LLM response claims 1.0" path seen pre-#81
      - structural_sub ≥ 0.5 — contact / sections / word-count reasonable

    If the composite meets the skip threshold but any critical dimension is
    low, we proceed with optimization anyway — the composite is misleading.
    """
    threshold = get_settings().ats_skip_threshold
    report = state.ats_score
    composite = report.score

    if composite < threshold:
        logger.info(
            "Routing: composite %.2f < threshold %.2f — proceeding with optimization",
            composite,
            threshold,
        )
        return "optimize"

    # Composite is high enough — but check the sub-dimensions aren't hiding
    # a degraded report.
    hard_coverage = _coverage_ratio(report.hard_skills)
    structural_ok = _structural_signal(report)
    has_llm_data = bool(report.hard_skills) or bool(report.soft_skills)

    if not has_llm_data:
        logger.info(
            "Routing: composite %.2f >= threshold but no LLM keyword data — "
            "proceeding with optimization (degraded ATS report)",
            composite,
        )
        return "optimize"
    if hard_coverage < 0.7 or structural_ok < 0.5:
        logger.info(
            "Routing: composite %.2f >= threshold but sub-dimensions weak "
            "(hard_coverage=%.2f, structural=%.2f) — proceeding with optimization",
            composite,
            hard_coverage,
            structural_ok,
        )
        return "optimize"

    logger.info(
        "Routing: composite %.2f >= threshold %.2f, sub-dimensions healthy — skipping optimization",
        composite,
        threshold,
    )
    return "skip"


def _coverage_ratio(hard_skills: list[SkillCountRow]) -> float:
    jd_asked = [r for r in hard_skills if r.jd_count >= 1]
    if not jd_asked:
        return 0.0  # no JD signal — can't vouch for coverage
    matched = sum(1 for r in jd_asked if r.resume_count >= 1)
    return matched / len(jd_asked)


def _structural_signal(report: ATSReport) -> float:
    """Same 8-boolean average `ats_score` uses; duplicated here so the graph
    doesn't import the orchestrator (keeps node dependencies one-way)."""
    flags = [
        report.contact.email_present,
        report.contact.phone_present,
        report.contact.address_present,
        report.sections.summary,
        report.sections.experience,
        report.sections.education,
        report.sections.skills,
        report.word_count_ok,
    ]
    return sum(1 for f in flags if f) / len(flags)


def _route_input(state: ResumeOptimizerState) -> str:
    """Route initial input: master YAML takes precedence over PDF."""
    if state.master_path:
        return "load_master"
    return "parse_resume"


def build_graph() -> CompiledStateGraph[Any]:
    """Build and compile the full resume optimization graph.

    Supports two input contracts:
      - `master_path` set → `load_master` (preferred, no LLM for ingestion)
      - `resume_path` set → `parse_resume` (legacy PDF-first flow)
    """
    graph = StateGraph(ResumeOptimizerState)

    graph.add_node("load_master", load_master_node)
    graph.add_node("parse_resume", parse_resume)
    graph.add_node("ats_score", ats_score)
    graph.add_node("analyze_gaps", analyze_gaps)
    graph.add_node("optimize_content", optimize_content)
    graph.add_node("generate_pdf", generate_pdf)
    graph.add_node("report_results", report_results)

    graph.add_conditional_edges(
        START,
        _route_input,
        {"load_master": "load_master", "parse_resume": "parse_resume"},
    )
    graph.add_edge("load_master", "ats_score")
    graph.add_edge("parse_resume", "ats_score")
    graph.add_conditional_edges(
        "ats_score",
        _route_after_ats_score,
        {"optimize": "analyze_gaps", "skip": "report_results"},
    )
    graph.add_edge("analyze_gaps", "optimize_content")
    graph.add_edge("optimize_content", "generate_pdf")
    graph.add_edge("generate_pdf", "report_results")
    graph.add_edge("report_results", END)

    return graph.compile()


def build_score_graph() -> CompiledStateGraph[Any]:
    """Build a partial graph for input-load + ATS score only."""
    graph = StateGraph(ResumeOptimizerState)

    graph.add_node("load_master", load_master_node)
    graph.add_node("parse_resume", parse_resume)
    graph.add_node("ats_score", ats_score)

    graph.add_conditional_edges(
        START,
        _route_input,
        {"load_master": "load_master", "parse_resume": "parse_resume"},
    )
    graph.add_edge("load_master", "ats_score")
    graph.add_edge("parse_resume", "ats_score")
    graph.add_edge("ats_score", END)

    return graph.compile()


def build_tailor_graph() -> CompiledStateGraph[Any]:
    """Tailor-only graph used as the body of the #78 iterative approval loop.

    Stops at `ats_score_tailored` so the CLI can gate the user between
    iterations without triggering PDF generation every pass.

    Shape:
      START → load_master/parse_resume → ats_score → [skip?] → analyze_gaps →
        optimize_content → ats_score_tailored → END

    The #44 skip gate still applies: when the initial ats_score on the master
    meets the threshold, the graph jumps straight to END without tailoring,
    and the CLI treats that as "no loop, render as-is".
    """
    graph = StateGraph(ResumeOptimizerState)

    graph.add_node("load_master", load_master_node)
    graph.add_node("parse_resume", parse_resume)
    graph.add_node("ats_score", ats_score)
    graph.add_node("analyze_gaps", analyze_gaps)
    graph.add_node("optimize_content", optimize_content)
    graph.add_node("ats_score_tailored", ats_score_tailored)

    graph.add_conditional_edges(
        START,
        _route_input,
        {"load_master": "load_master", "parse_resume": "parse_resume"},
    )
    graph.add_edge("load_master", "ats_score")
    graph.add_edge("parse_resume", "ats_score")
    graph.add_conditional_edges(
        "ats_score",
        _route_after_ats_score,
        {"optimize": "analyze_gaps", "skip": END},
    )
    graph.add_edge("analyze_gaps", "optimize_content")
    graph.add_edge("optimize_content", "ats_score_tailored")
    graph.add_edge("ats_score_tailored", END)

    return graph.compile()


def build_finalize_graph() -> CompiledStateGraph[Any]:
    """PDF + report-results graph, run once after the #78 loop exits."""
    graph = StateGraph(ResumeOptimizerState)
    graph.add_node("generate_pdf", generate_pdf)
    graph.add_node("report_results", report_results)
    graph.add_edge(START, "generate_pdf")
    graph.add_edge("generate_pdf", "report_results")
    graph.add_edge("report_results", END)
    return graph.compile()
