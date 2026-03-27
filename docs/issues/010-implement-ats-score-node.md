# [Feature]: Implement and test ats_score node

## Description

Implement the ATS scoring node. It takes the parsed `ResumeData` and `JobDescription` from state, sends them to the LLM with the ATS scoring prompt template, and returns an `ATSScore` with score, reasoning, keyword matches, and keyword gaps. Then write unit tests with mocked LLM.

## Motivation

ATS scoring is the core value proposition — telling users how well their resume matches a job description. This is the first node that depends on a prior node's output (parse_resume), introducing state flow between nodes. Tests ensure the score parsing is reliable and edge cases (LLM errors, malformed JSON) are handled gracefully.

## Tasks

### Implementation

- [x] Import `tools.llm_provider.get_llm` and `prompts.ats_scoring.ATS_SCORE`
- [x] Serialize `state.resume` to JSON for the prompt (use `.model_dump_json()`)
- [x] Format the `ATS_SCORE` template with resume JSON and `state.job_description.raw_text`
- [x] Call `get_llm().invoke()` with formatted prompt
- [x] Parse JSON response into `ATSScore` fields
- [x] Return `{"ats_score": ATSScore(...)}`
- [x] Error handling: catch exceptions, append to `state.errors`, return `{"errors": errors}`
- [x] Score clamping: `max(0.0, min(1.0, score))` ensures score stays in 0.0–1.0 range
- [x] Null coercion: `.get("field") or default` for all ATSScore fields
- [x] Logging: INFO on node entry/exit with key metrics (score, match count, gap count)

### Tests

- [x] Create `tests/test_ats_score.py`
- [x] Use `sample_state` fixture from `conftest.py` for input state
- [x] Mock `get_llm` to return known JSON matching `ATSScore` schema
- [x] Test: `test_scores_resume_successfully` — verify score, reasoning, matches, gaps populated
- [x] Test: `test_handles_llm_error` — mock LLM to raise, verify error recorded, no ats_score in result
- [x] Test: `test_handles_invalid_json` — mock malformed response, verify error recorded
- [x] Test: `test_clamps_score_above_one` — verify score > 1.0 clamped to 1.0
- [x] Test: `test_clamps_score_below_zero` — verify score < 0.0 clamped to 0.0
- [x] Test: `test_handles_null_fields` — verify null fields coerced to defaults
- [x] Test: `test_returns_only_changed_fields` — verify result keys subset of {ats_score, errors}

## Acceptance Criteria

- [x] Node returns `{"ats_score": ATSScore(...)}` with populated fields
- [x] Uses prompt template, not inline strings
- [x] Errors caught and recorded, pipeline continues
- [x] All tests pass with mocked LLM, uses existing `sample_state` fixture
- [x] 7 tests pass, ruff lint clean, ruff format clean, mypy clean (52/52 total tests pass)

## Key Files

- `src/resume_operator/nodes/ats_score.py`
- `src/resume_operator/prompts/ats_scoring.py`
- `tests/test_ats_score.py` (new)

## Dependencies

- #006

## Labels

`enhancement`, `priority:high`
