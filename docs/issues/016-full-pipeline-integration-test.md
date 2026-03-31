# [Feature]: Full pipeline integration test with mocked LLM

## Description

Write an integration test that runs the complete LangGraph pipeline from `parse_resume` through `report_results` with all LLM calls mocked. This verifies state flows correctly through all six nodes and the graph edges work end-to-end.

## Motivation

Individual node tests verify each piece works in isolation. This integration test verifies they work together — state flows correctly between nodes, and the full pipeline produces the expected final state.

## LangGraph Concepts Reinforced

- **Full graph execution**: invoke with initial state, get final state
- **State accumulation**: each node adds to the state, subsequent nodes read it
- **Error resilience**: pipeline continues when individual nodes fail

## Tasks

- [x] Create `tests/test_integration.py`
- [x] Mock `get_llm` at each node's import site (4 separate patches) with pre-canned JSON responses
- [x] Mock `pdf_parser.extract_text` to return sample resume text
- [x] Mock `pdf_generator.generate_pdf` to return a mock Path without creating a file
- [x] Mock `report_results.RESULTS_PATH` to redirect JSON output to `tmp_path`
- [x] Invoke the compiled graph with initial state (resume_path, job_description_text, output_path)
- [x] Verify final state has: populated `resume`, `ats_score`, `gap_analysis`, `optimized_resume`, `output_path`, `report`
- [x] Verify `errors` list is empty (happy path)
- [x] Test: `test_pipeline_continues_on_node_error` — ats_score's `get_llm` raises RuntimeError, pipeline completes with errors recorded, downstream nodes still populate their fields

## Acceptance Criteria

- Full pipeline runs with mocked I/O
- All state fields populated after run
- Pipeline continues when individual nodes fail
- No real files or API calls

## Key Files

- `tests/test_integration.py` (new)
- `src/resume_operator/graph.py`

## Dependencies

- #014, #015

## Labels

`enhancement`, `priority:high`
