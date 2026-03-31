# [Feature]: Add input validation and graceful error messages

## Description

Add validation for CLI inputs and state preconditions. Users should see clear, helpful error messages instead of Python tracebacks when something is wrong.

## Motivation

A good user experience starts with clear error messages. "File not found: resume.pdf" is infinitely better than a 20-line Python traceback. This is especially important since the tool handles personal data (resumes).

## Tasks

- [x] In `main.py`: validate resume file exists and is `.pdf` via `_validate_resume()`, validate job file exists and is readable via `_validate_job()` — applied to all 3 commands (`run`, `score`, `parse-resume`)
- [x] In `parse_resume` node: validate `state.resume_path` is non-empty before processing — returns early with error if empty
- [x] In `ats_score` node: validate `state.resume.raw_text` is non-empty — skips scoring with warning + error if empty
- [x] In `generate_pdf` node: validate `state.optimized_resume.sections` is non-empty — skips PDF generation with warning + error if empty
- [x] Use `typer.BadParameter` for CLI validation errors (replaced `console.print` + `typer.Exit` pattern)
- [x] Add Rich `Panel` for runtime error display in `run` command (red-bordered panel)
- [x] Add `--dry-run` flag to `run` command — validates inputs, shows green-bordered Panel with resume/job/output paths, exits without invoking graph
- [x] Add 7 new tests: CLI (.pdf check, dry-run, dry-run with invalid file) + node preconditions (empty resume_path, empty resume data, empty sections)

## Acceptance Criteria

- Invalid inputs produce clear error messages, not stack traces
- Nodes skip gracefully when preconditions aren't met (record error, continue)
- `--dry-run` validates inputs and shows what would be executed

## Key Files

- `src/resume_operator/main.py`
- All files in `src/resume_operator/nodes/`

## Dependencies

- #017

## Labels

`enhancement`, `priority:medium`
