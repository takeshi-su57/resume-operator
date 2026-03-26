# [Feature]: Implement and test optimize_content node

## Description

Implement the content optimization node. It takes the full accumulated state (resume, job, gap analysis) and asks the LLM to rewrite resume sections for better ATS compatibility. Returns an `OptimizedResume` with rewritten sections and a change log. Then write unit tests with mocked LLM.

## Motivation

This is the core transformation — turning gap analysis into an improved resume. The LLM rewrites sections to incorporate missing keywords, emphasize relevant experience, and improve overall match while keeping the profile authentic. Tests ensure the output structure is correct and errors are handled gracefully.

## Tasks

### Implementation

- [ ] Import `tools.llm_provider.get_llm` and `prompts.content_optimization.OPTIMIZE_CONTENT`
- [ ] Format the template with resume JSON, job description, and gap analysis JSON
- [ ] Call LLM and parse JSON response into `OptimizedResume` fields
- [ ] Return `{"optimized_resume": OptimizedResume(...)}`
- [ ] Error handling: on failure, return empty `OptimizedResume` and record error

### Tests

- [ ] Create `tests/test_optimize_content.py`
- [ ] Test: `test_optimizes_content_successfully` — mock LLM, verify sections and changes
- [ ] Test: `test_handles_llm_error` — verify error recorded
- [ ] Test: `test_preserves_all_section_keys` — verify output has summary, experience, skills, education

## Acceptance Criteria

- Node returns `{"optimized_resume": OptimizedResume(...)}` with sections dict and changes_made list
- Sections dict keys match the prompt template (summary, experience, skills, education)
- Error handling consistent with other nodes
- All tests pass with mocked LLM, uses `sample_state` fixture

## Key Files

- `src/resume_operator/nodes/optimize_content.py`
- `src/resume_operator/prompts/content_optimization.py`
- `tests/test_optimize_content.py` (new)

## Dependencies

- #013

## Labels

`enhancement`, `priority:high`
