# [Feature]: Wire parse-resume CLI command to the graph

## Description

Connect the `parse-resume` CLI command in `main.py` so it actually invokes the LangGraph pipeline (parse_resume node only) and displays the extracted resume data with Rich formatting.

## Motivation

This is the first time the user sees the system work end-to-end: PDF → LLM → structured data → terminal output. It validates the full stack from CLI to LangGraph to tools.

## Tasks

- [ ] In `main.py`, import `build_graph` or create a helper for a single-node graph
- [ ] In `parse_resume` command: validate file exists, build initial state, invoke graph
- [ ] Display results using Rich: name, email, skills list, experience count, education count
- [ ] Handle errors: show `state.errors` if any, with `[red]` Rich styling
- [ ] Add Rich `Status` spinner while the pipeline runs

## Acceptance Criteria

- `python -m resume_operator parse-resume --resume test.pdf` runs and displays results
- Errors displayed in red
- Progress spinner shown during execution

## Key Files

- `src/resume_operator/main.py`
- `src/resume_operator/graph.py`

## Dependencies

- #006

## Labels

`enhancement`, `priority:medium`
