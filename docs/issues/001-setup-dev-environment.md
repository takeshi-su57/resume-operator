# [Chore]: Set up development environment and verify project installs cleanly

## Description

The project has `pyproject.toml` and stub files but no verification that everything installs and all tooling runs cleanly. This issue ensures the full dev environment works end-to-end.

## Motivation

A clean baseline is required before any implementation begins. All quality tools (ruff, mypy, pytest) must pass on the stub codebase so regressions are detectable immediately.

## Tasks

- [ ] Run `pip install -e ".[dev]"` and confirm it succeeds
- [ ] Run `ruff check src/ tests/` and fix any lint errors in stubs
- [ ] Run `ruff format src/ tests/` and commit formatting changes
- [ ] Run `mypy src/` in strict mode and fix any type errors in stubs
- [ ] Run `pytest` and confirm `test_state.py` passes
- [ ] Add `py.typed` marker file to `src/resume_operator/`
- [ ] Verify `python -m resume_operator --help` shows CLI help

## Acceptance Criteria

- All five quality commands pass with zero errors
- CLI shows help text with `run`, `parse-resume`, and `score` commands
- Existing `test_state.py` tests pass

## Key Files

- `pyproject.toml`
- `src/resume_operator/__init__.py`
- `tests/test_state.py`

## Dependencies

None — this is the first issue.

## Labels

`chore`, `priority:high`
