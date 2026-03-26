# [Feature]: Wire run and score CLI commands to the graph

## Description

Complete the CLI by wiring the `run` and `score` commands to invoke the full graph and partial graph respectively. Add Rich progress display showing pipeline execution status.

## Motivation

This makes the system usable end-to-end from the command line. Users can run the full optimization pipeline or just get a quick ATS score — both with clear, formatted output.

## Tasks

- [ ] In `run` command: validate files exist, build initial state, invoke `build_graph()`, display results with Rich table (ATS score, gaps, changes, output path)
- [ ] In `score` command: build a partial graph with only `parse_resume` and `ats_score` nodes, invoke and display score
- [ ] Add Rich `Progress` or `Status` context for pipeline execution
- [ ] Display errors in `[red]` if any occurred
- [ ] Color-code ATS score: green >= 0.7, yellow >= 0.4, red < 0.4

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
