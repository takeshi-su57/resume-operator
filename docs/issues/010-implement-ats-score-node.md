# [Feature]: Implement and test ats_score node

## Description

Implement the ATS scoring node. It takes the parsed `ResumeData` and `JobDescription` from state, sends them to the LLM with the ATS scoring prompt template, and returns an `ATSScore` with score, reasoning, keyword matches, and keyword gaps. Then write unit tests with mocked LLM.

## Motivation

ATS scoring is the core value proposition — telling users how well their resume matches a job description. This is the first node that depends on a prior node's output (parse_resume), introducing state flow between nodes. Tests ensure the score parsing is reliable and edge cases (LLM errors, malformed JSON) are handled gracefully.

## Tasks

### Implementation

- [ ] Import `tools.llm_provider.get_llm` and `prompts.ats_scoring.ATS_SCORE`
- [ ] Serialize `state.resume` to JSON for the prompt (use `.model_dump_json()`)
- [ ] Format the `ATS_SCORE` template with resume JSON and `state.job_description.raw_text`
- [ ] Call `get_llm().invoke()` with formatted prompt
- [ ] Parse JSON response into `ATSScore` fields
- [ ] Return `{"ats_score": ATSScore(...)}`
- [ ] Error handling: catch exceptions, append to `state.errors`, return default `ATSScore`

### Tests

- [ ] Create `tests/test_ats_score.py`
- [ ] Use `sample_state` fixture from `conftest.py` for input state
- [ ] Mock `get_llm` to return known JSON matching `ATSScore` schema
- [ ] Test: `test_scores_resume_successfully` — verify score, matches, gaps populated
- [ ] Test: `test_handles_llm_error` — mock LLM to raise, verify error recorded
- [ ] Test: `test_handles_invalid_json` — mock malformed response, verify error recorded
- [ ] Test: `test_score_range_validation` — verify score is between 0.0 and 1.0

## Acceptance Criteria

- Node returns `{"ats_score": ATSScore(...)}` with populated fields
- Uses prompt template, not inline strings
- Errors caught and recorded, pipeline continues
- All tests pass with mocked LLM, uses existing `sample_state` fixture

## Key Files

- `src/resume_operator/nodes/ats_score.py`
- `src/resume_operator/prompts/ats_scoring.py`
- `tests/test_ats_score.py` (new)

## Dependencies

- #006

## Labels

`enhancement`, `priority:high`
