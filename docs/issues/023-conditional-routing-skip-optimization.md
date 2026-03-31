# [Feature]: Add conditional routing — skip optimization when ATS score is high

## Description

Add a LangGraph conditional edge that skips `optimize_content` and `generate_pdf` when the ATS score is already above a configurable threshold (default 0.9). This introduces conditional edges in LangGraph.

## Motivation

If a resume already scores 0.95 against a job description, optimizing it would be unnecessary or could even make it worse. Conditional routing is also a key LangGraph concept needed for future batch mode.

## LangGraph Concepts Introduced

- **Conditional edges**: `graph.add_conditional_edges("node", routing_fn, mapping)`
- **Routing functions**: `(state) -> str` that returns the next node name
- **Edge mappings**: dict mapping routing function return values to node names

## Tasks

- [x] Add `ats_skip_threshold: float = 0.9` to `config.py` Settings class
- [x] Add `ATS_SKIP_THRESHOLD=0.9` to `.env.example`
- [x] In `graph.py`, replace `ats_score -> analyze_gaps` edge with `add_conditional_edges` using `_route_after_ats_score` routing function
- [x] Define routing function: reads threshold from config, returns `"skip"` if score >= threshold, `"optimize"` otherwise, with INFO logging of the routing decision
- [x] Use `graph.add_conditional_edges("ats_score", _route_after_ats_score, {"optimize": "analyze_gaps", "skip": "report_results"})`
- [x] Update `report_results` to include `optimization_skipped` field in report (derived from empty `optimized_resume.sections`)
- [x] Write 4 routing tests in `test_graph.py::TestConditionalRouting`: high score, exact threshold, low score, zero/default score
- [x] Create `docs/architecture.md` with conditional flow ASCII diagram, component table, data flow, and error handling description
- [x] Update `tests/test_report_results.py` expected keys to include `optimization_skipped`

## Acceptance Criteria

- High ATS score (>= 0.9) skips optimization and goes to report
- Low ATS score follows the normal path through all nodes
- Threshold is configurable via env var
- Routing logic has test coverage
- `docs/architecture.md` updated with conditional flow diagram

## Key Files

- `src/resume_operator/graph.py`
- `src/resume_operator/config.py`
- `tests/test_graph.py`
- `docs/architecture.md`

## Dependencies

- #016

## Labels

`enhancement`, `priority:low`
