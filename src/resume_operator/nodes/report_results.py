"""Node: Save optimization results to JSON."""

from resume_operator.state import ResumeOptimizerState


def report_results(state: ResumeOptimizerState) -> dict:
    """Compile and save the full optimization report.

    Writes a JSON report to data/ with ATS scores, gap analysis,
    changes made, and any errors encountered.
    """
    # TODO: Build report dict from state fields
    # TODO: Write JSON to data/results.json
    return {}
