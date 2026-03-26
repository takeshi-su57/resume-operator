# [Feature]: Implement optimize_content node

## Description

Implement the content optimization node. It takes the full accumulated state (resume, job, gap analysis) and asks the LLM to rewrite resume sections for better ATS compatibility. Returns an `OptimizedResume` with rewritten sections and a change log.

## Motivation

This is the core transformation — turning gap analysis into an improved resume. The LLM rewrites sections to incorporate missing keywords, emphasize relevant experience, and improve overall match while keeping the profile authentic.

## Tasks

- [ ] Import `tools.llm_provider.get_llm` and `prompts.content_optimization.OPTIMIZE_CONTENT`
- [ ] Format the template with resume JSON, job description, and gap analysis JSON
- [ ] Call LLM and parse JSON response into `OptimizedResume` fields
- [ ] Return `{"optimized_resume": OptimizedResume(...)}`
- [ ] Error handling: on failure, return empty `OptimizedResume` and record error

## Acceptance Criteria

- Node returns `{"optimized_resume": OptimizedResume(...)}` with sections dict and changes_made list
- Sections dict keys match the prompt template (summary, experience, skills, education)
- Error handling consistent with other nodes

## Key Files

- `src/resume_operator/nodes/optimize_content.py`
- `src/resume_operator/prompts/content_optimization.py`

## Dependencies

- #013

## Labels

`enhancement`, `priority:high`
