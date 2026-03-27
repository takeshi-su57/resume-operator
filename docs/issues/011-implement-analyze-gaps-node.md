# [Feature]: Implement and test analyze_gaps node

## Description

Implement the gap analysis node. It reads resume data, job description, and ATS score from state, sends them to the LLM with the gap analysis prompt template, and returns a `GapAnalysis` with gaps, strengths, and suggestions. Then write unit tests with mocked LLM.

## Motivation

Gap analysis turns a numeric ATS score into actionable insights. Users need to know specifically what's missing from their resume and what they can improve. Tests ensure the node correctly parses LLM responses and handles failures without crashing the pipeline.

## Tasks

### Implementation

- [ ] Import `tools.llm_provider.get_llm` and `prompts.gap_analysis.ANALYZE_GAPS`
- [ ] Format the template with resume JSON, job description text, ATS score, and keyword gaps
- [ ] Call LLM and parse JSON response into `GapAnalysis` fields
- [ ] Return `{"gap_analysis": GapAnalysis(...)}`
- [ ] Error handling matching the established pattern

### Tests

- [ ] Create `tests/test_analyze_gaps.py`
- [ ] Test: `test_analyzes_gaps_successfully` — mock LLM, verify gaps/strengths/suggestions
- [ ] Test: `test_handles_llm_error` — verify error recorded

## Acceptance Criteria

- Node returns `{"gap_analysis": GapAnalysis(...)}` with gaps, strengths, suggestions
- Uses prior state fields (`ats_score`) as input
- Follows same error handling pattern as other nodes
- All tests pass with mocked LLM, uses `sample_state` fixture

## Key Files

- `src/resume_operator/nodes/analyze_gaps.py`
- `src/resume_operator/prompts/gap_analysis.py`
- `tests/test_analyze_gaps.py` (new)

## Dependencies

- #010

## Labels

`enhancement`, `priority:high`
