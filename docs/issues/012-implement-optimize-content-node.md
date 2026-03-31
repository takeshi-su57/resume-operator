# [Feature]: Implement and test optimize_content node

## Description

Implement the content optimization node. It takes the full accumulated state (resume, job, gap analysis) and asks the LLM to rewrite resume sections for better ATS compatibility. Returns an `OptimizedResume` with rewritten sections and a change log. Then write unit tests with mocked LLM.

## Motivation

This is the core transformation — turning gap analysis into an improved resume. The LLM rewrites sections to incorporate missing keywords, emphasize relevant experience, and improve overall match while keeping the profile authentic. Tests ensure the output structure is correct and errors are handled gracefully.

## Tasks

### Implementation

- [x] Import `tools.llm_provider.get_llm` and `prompts.content_optimization.OPTIMIZE_CONTENT`
- [x] Format the template with resume JSON, job description, and gap analysis JSON
- [x] Call LLM and parse JSON response into `OptimizedResume` fields
- [x] Return `{"optimized_resume": OptimizedResume(...)}`
- [x] Error handling: on failure, record error and return `{"errors": [...]}`  (no empty OptimizedResume — matches analyze_gaps/ats_score pattern)
- [x] Logging: entry, completion metrics (section count, changes count), and errors

### Tests

- [x] Create `tests/test_optimize_content.py`
- [x] Test: `test_optimizes_content_successfully` — mock LLM, verify sections and changes
- [x] Test: `test_handles_llm_error` — verify error recorded, no optimized_resume returned
- [x] Test: `test_handles_invalid_json` — verify invalid JSON error recorded
- [x] Test: `test_handles_null_fields` — verify null coerced to empty dict/list
- [x] Test: `test_preserves_all_section_keys` — verify output has summary, experience, skills, education
- [x] Test: `test_returns_only_changed_fields` — verify no extra state keys leaked

## Acceptance Criteria

- [x] Node returns `{"optimized_resume": OptimizedResume(...)}` with sections dict and changes_made list
- [x] Sections dict keys match the prompt template (summary, experience, skills, education)
- [x] Error handling consistent with other nodes (analyze_gaps/ats_score pattern)
- [x] All 6 tests pass with mocked LLM, uses `sample_state` fixture
- [x] ruff, mypy clean

## Key Files

- `src/resume_operator/nodes/optimize_content.py`
- `src/resume_operator/prompts/content_optimization.py`
- `tests/test_optimize_content.py` (new)

## Dependencies

- #011

## Labels

`enhancement`, `priority:high`
