# [Feature]: Write unit tests for analyze_gaps and optimize_content nodes

## Description

Test both LLM analysis nodes since they follow the same pattern. Each needs happy path and error path coverage with mocked LLM.

## Motivation

These two nodes form the analytical core of the pipeline. Testing ensures they correctly parse LLM responses and handle failures without crashing the pipeline.

## Tasks

- [ ] Create `tests/test_analyze_gaps.py`
- [ ] Test: `test_analyzes_gaps_successfully` — mock LLM, verify gaps/strengths/suggestions
- [ ] Test: `test_handles_llm_error` — verify error recorded
- [ ] Create `tests/test_optimize_content.py`
- [ ] Test: `test_optimizes_content_successfully` — mock LLM, verify sections and changes
- [ ] Test: `test_handles_llm_error` — verify error recorded
- [ ] Test: `test_preserves_all_section_keys` — verify output has summary, experience, skills, education

## Acceptance Criteria

- All tests pass with mocked LLM
- Both nodes have happy path + error path coverage
- Uses `sample_state` fixture

## Key Files

- `tests/test_analyze_gaps.py` (new)
- `tests/test_optimize_content.py` (new)

## Dependencies

- #013, #014

## Labels

`enhancement`, `priority:high`
