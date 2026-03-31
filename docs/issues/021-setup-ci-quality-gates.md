# [Chore]: Set up CI quality gates (GitHub Actions)

## Description

Configure automated quality checks that run on every commit or PR. This ensures ruff, mypy, and pytest always pass before code is merged.

## Motivation

Automated CI prevents quality regressions. Every PR should pass lint, type check, and tests before merging — catching issues early instead of in production.

## Tasks

- [x] Create `.github/workflows/ci.yml` with a Python 3.12 job on ubuntu-latest
- [x] Steps: checkout, install uv (`astral-sh/setup-uv@v4`), install Python 3.12 via uv, `uv sync --dev`, ruff check, ruff format --check, mypy, pytest --tb=short
- [x] Add `pytest --tb=short` for concise test output in CI
- [x] Add CI badge to `README.md` linking to Actions workflow page
- [x] CI triggers on push to `main` and on all pull requests
- [x] Created `.pre-commit-config.yaml` with ruff check (--fix) and ruff-format hooks via `ruff-pre-commit`

## Acceptance Criteria

- CI runs ruff check, ruff format --check, mypy strict, and pytest
- CI fails if any check fails
- README shows CI status badge

## Key Files

- `.github/workflows/ci.yml` (new)
- `README.md`

## Dependencies

- #016

## Labels

`chore`, `priority:medium`
