# [Feature]: Wire run and score CLI commands to the graph

## Description

Complete the CLI by wiring the `run` and `score` commands to invoke the full graph and partial graph respectively. Add Rich progress display showing pipeline execution status.

## Motivation

This makes the system usable end-to-end from the command line. Users can run the full optimization pipeline or just get a quick ATS score — both with clear, formatted output.

## Tasks

- [x] In `run` command: validate files exist, build initial state, invoke `build_graph()`, display results with Rich formatting (ATS score, gaps, changes, output path)
- [x] In `score` command: added `build_score_graph()` in `graph.py` with only `parse_resume` and `ats_score` nodes, wired into CLI with file validation, Rich output, and `--verbose` flag
- [x] Add Rich `Status` spinner context for both `run` and `score` pipeline execution
- [x] Display errors in `[red]` if any occurred
- [x] Color-code ATS score via `_score_color()` helper: green >= 0.7, yellow >= 0.4, red < 0.4
- [x] Display optimization changes (`optimized_resume.changes_made`) in `run` output
- [x] Display output PDF path in `run` output
- [x] Add 7 new CLI tests: `TestRunCommand` (3 tests) + `TestScoreCommand` (4 tests)

## Acceptance Criteria

- `python -m resume_operator run --resume r.pdf --job j.txt` runs full pipeline and displays results
- `python -m resume_operator score --resume r.pdf --job j.txt` runs parse + score only
- Progress indicator shown during execution
- Results displayed with Rich formatting and color coding

## Key Files

- `src/resume_operator/main.py`
- `src/resume_operator/graph.py`

## Dependencies

- #016

## Labels

`enhancement`, `priority:high`
