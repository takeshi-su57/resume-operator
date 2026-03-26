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

- [ ] Create `tests/test_integration.py`
- [ ] Mock `get_llm` to return pre-canned JSON responses for each node's expected prompt
- [ ] Mock `pdf_parser.extract_text` to return sample resume text
- [ ] Mock `pdf_generator.generate_pdf` to return a path without creating a file
- [ ] Invoke the compiled graph with initial state (resume_path, job_description_path, output_path)
- [ ] Verify final state has: populated `resume`, `ats_score`, `gap_analysis`, `optimized_resume`, `output_path`, `report`
- [ ] Verify `errors` list is empty (happy path)
- [ ] Test: `test_pipeline_continues_on_node_error` — make one node fail, verify pipeline completes with errors recorded

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
