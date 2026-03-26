"""LangGraph StateGraph assembly for the resume optimization pipeline."""

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from resume_operator.nodes.analyze_gaps import analyze_gaps
from resume_operator.nodes.ats_score import ats_score
from resume_operator.nodes.generate_pdf import generate_pdf
from resume_operator.nodes.optimize_content import optimize_content
from resume_operator.nodes.parse_resume import parse_resume
from resume_operator.nodes.report_results import report_results
from resume_operator.state import ResumeOptimizerState


def build_graph() -> CompiledStateGraph[Any]:
    """Build and compile the resume optimization graph."""
    graph = StateGraph(ResumeOptimizerState)

    # Register nodes
    graph.add_node("parse_resume", parse_resume)
    graph.add_node("ats_score", ats_score)
    graph.add_node("analyze_gaps", analyze_gaps)
    graph.add_node("optimize_content", optimize_content)
    graph.add_node("generate_pdf", generate_pdf)
    graph.add_node("report_results", report_results)

    # Linear pipeline edges
    graph.add_edge(START, "parse_resume")
    graph.add_edge("parse_resume", "ats_score")
    graph.add_edge("ats_score", "analyze_gaps")
    graph.add_edge("analyze_gaps", "optimize_content")
    graph.add_edge("optimize_content", "generate_pdf")
    graph.add_edge("generate_pdf", "report_results")
    graph.add_edge("report_results", END)

    return graph.compile()
