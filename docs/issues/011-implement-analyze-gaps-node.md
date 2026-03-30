# [Feature]: Implement and test analyze_gaps node

## Description

Implement the gap analysis node. It reads resume data, job description, and ATS score from state, sends them to the LLM with the gap analysis prompt template, and returns a `GapAnalysis` with gaps, strengths, and suggestions. Then write unit tests with mocked LLM.

## Motivation

Gap analysis turns a numeric ATS score into actionable insights. Users need to know specifically what's missing from their resume and what they can improve. Tests ensure the node correctly parses LLM responses and handles failures without crashing the pipeline.

## Tasks

### Implementation

- [x] Import `tools.llm_provider.get_llm` and `prompts.gap_analysis.ANALYZE_GAPS`
- [x] Format the template with resume JSON, job description text, ATS score, and keyword gaps
- [x] Call LLM and parse JSON response into `GapAnalysis` fields
- [x] Return `{"gap_analysis": GapAnalysis(...)}`
- [x] Error handling matching the established pattern
- [x] Wire `run` CLI command to invoke the full LangGraph pipeline (was a TODO stub)
- [x] Add `--verbose` flag to `run` command for debug logging
- [x] Display parsed resume, ATS score, and gap analysis results in CLI output

### Tests

- [x] Create `tests/test_analyze_gaps.py`
- [x] Test: `test_analyzes_gaps_successfully` — mock LLM, verify gaps/strengths/suggestions
- [x] Test: `test_handles_llm_error` — verify error recorded
- [x] Test: `test_handles_invalid_json` — verify invalid JSON error recorded
- [x] Test: `test_handles_null_fields` — verify null coercion to empty lists
- [x] Test: `test_returns_only_changed_fields` — verify no extra state keys returned

## Acceptance Criteria

- [x] Node returns `{"gap_analysis": GapAnalysis(...)}` with gaps, strengths, suggestions
- [x] Uses prior state fields (`ats_score`) as input
- [x] Follows same error handling pattern as other nodes
- [x] All tests pass with mocked LLM, uses `sample_state` fixture
- [x] Full test suite (57 tests) passes
- [x] Ruff lint and mypy type check pass
- [x] `run` CLI command invokes the full pipeline end-to-end

## Implementation Details

### analyze_gaps node (`src/resume_operator/nodes/analyze_gaps.py`)
- Formats `ANALYZE_GAPS` prompt with `state.resume.model_dump_json()`, `state.job_description.raw_text`, `state.ats_score.score`, and `state.ats_score.keyword_gaps`
- Calls `get_llm().invoke(prompt)` and parses JSON response
- Coerces null fields to empty lists via `parsed.get("field") or []`
- Handles `JSONDecodeError` and general exceptions, appending to `state.errors`
- Logs at INFO level on start/completion with gap/strength/suggestion counts

### CLI `run` command (`src/resume_operator/main.py`)
- Validates resume and job file existence
- Invokes `build_graph().invoke()` with `resume_path`, `job_description_path`, `output_path`
- Displays parsed resume, ATS score, gap analysis with Rich formatting
- Supports `--verbose` / `-v` for debug logging
- Downstream stub nodes (`optimize_content`, `generate_pdf`, `report_results`) return `{}` harmlessly

## Key Files

- `src/resume_operator/nodes/analyze_gaps.py` — node implementation
- `src/resume_operator/main.py` — wired `run` command to invoke full pipeline
- `tests/test_analyze_gaps.py` (new) — 5 unit tests with mocked LLM

## Dependencies

- #010

## Labels

`enhancement`, `priority:high`
