# [Chore]: Set up CI quality gates (GitHub Actions)

## Description

Configure automated quality checks that run on every commit or PR. This ensures ruff, mypy, and pytest always pass before code is merged.

## Motivation

Automated CI prevents quality regressions. Every PR should pass lint, type check, and tests before merging — catching issues early instead of in production.

## Tasks

- [ ] Create `.github/workflows/ci.yml` with a Python 3.12 job
- [ ] Steps: checkout, install deps (`pip install -e ".[dev]"`), ruff check, ruff format --check, mypy, pytest
- [ ] Add `pytest --tb=short` for concise test output in CI
- [ ] Add a badge to `README.md` showing CI status
- [ ] Ensure CI runs on push to `main` and on all PRs
- [ ] Optionally: create `.pre-commit-config.yaml` with ruff hooks

## Acceptance Criteria

- CI runs ruff check, ruff format --check, mypy strict, and pytest
- CI fails if any check fails
- README shows CI status badge

## Key Files

- `.github/workflows/ci.yml` (new)
- `README.md`

## Dependencies

- #021

## Labels

`chore`, `priority:medium`
