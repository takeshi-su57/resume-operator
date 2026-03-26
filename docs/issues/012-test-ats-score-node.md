# [Feature]: Write unit tests for ats_score node

## Description

Test the ATS scoring node with mocked LLM. Verify it formats the prompt correctly, parses valid responses, and handles error cases.

## Motivation

ATS scoring produces the primary metric users care about. Tests ensure the score parsing is reliable and edge cases (LLM errors, malformed JSON) are handled gracefully.

## Tasks

- [ ] Create `tests/test_ats_score.py`
- [ ] Use `sample_state` fixture from `conftest.py` for input state
- [ ] Mock `get_llm` to return known JSON matching `ATSScore` schema
- [ ] Test: `test_scores_resume_successfully` — verify score, matches, gaps populated
- [ ] Test: `test_handles_llm_error` — mock LLM to raise, verify error recorded
- [ ] Test: `test_handles_invalid_json` — mock malformed response, verify error recorded
- [ ] Test: `test_score_range_validation` — verify score is between 0.0 and 1.0

## Acceptance Criteria

- All tests pass with mocked LLM
- Uses existing `sample_state` fixture

## Key Files

- `tests/test_ats_score.py` (new)
- `src/resume_operator/nodes/ats_score.py`

## Dependencies

- #011

## Labels

`enhancement`, `priority:high`
