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

- [ ] Add `ATS_SKIP_THRESHOLD` to `config.py` Settings class (default: 0.9)
- [ ] Add `ATS_SKIP_THRESHOLD=0.9` to `.env.example`
- [ ] In `graph.py`, replace the `ats_score -> analyze_gaps` edge with a conditional edge
- [ ] Define routing function: if `state.ats_score.score >= threshold`, route to `report_results`; else route to `analyze_gaps`
- [ ] Use `graph.add_conditional_edges("ats_score", routing_fn, {"optimize": "analyze_gaps", "skip": "report_results"})`
- [ ] Update `report_results` to note whether optimization was skipped
- [ ] Write tests in `test_graph.py`: verify routing for scores above and below threshold

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

- #021

## Labels

`enhancement`, `priority:low`
