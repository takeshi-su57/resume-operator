# [Feature]: Add input validation and graceful error messages

## Description

Add validation for CLI inputs and state preconditions. Users should see clear, helpful error messages instead of Python tracebacks when something is wrong.

## Motivation

A good user experience starts with clear error messages. "File not found: resume.pdf" is infinitely better than a 20-line Python traceback. This is especially important since the tool handles personal data (resumes).

## Tasks

- [ ] In `main.py`: validate resume file exists and is a `.pdf`, validate job file exists and is readable
- [ ] In `parse_resume` node: validate `state.resume_path` is non-empty before processing
- [ ] In `ats_score` node: validate `state.resume.raw_text` is non-empty (parse_resume must have succeeded)
- [ ] In `generate_pdf` node: validate `state.optimized_resume.sections` is non-empty
- [ ] Use `typer.BadParameter` for CLI validation errors
- [ ] Add Rich error panels for runtime errors
- [ ] Add a `--dry-run` flag to `run` command that validates inputs without executing

## Acceptance Criteria

- Invalid inputs produce clear error messages, not stack traces
- Nodes skip gracefully when preconditions aren't met (record error, continue)
- `--dry-run` validates inputs and shows what would be executed

## Key Files

- `src/resume_operator/main.py`
- All files in `src/resume_operator/nodes/`

## Dependencies

- #022

## Labels

`enhancement`, `priority:medium`
