# [Feature]: Wire parse-resume CLI command to the graph

## Description

Connect the `parse-resume` CLI command in `main.py` so it actually invokes the LangGraph pipeline (parse_resume node only) and displays the extracted resume data with Rich formatting.

## Motivation

This is the first time the user sees the system work end-to-end: PDF → LLM → structured data → terminal output. It validates the full stack from CLI to LangGraph to tools.

## Tasks

- [x] In `main.py`, import `build_graph` and invoke the full pipeline graph
- [x] In `parse_resume` command: validate file exists, build initial state, invoke graph
- [x] Display results using Rich: name, email, phone, skills list, experience/education/certifications counts
- [x] Handle errors: show `state.errors` if any, with `[red]` Rich styling
- [x] Add Rich `Status` spinner while the pipeline runs

## Acceptance Criteria

- `python -m resume_operator parse-resume --resume test.pdf` runs and displays results
- Errors displayed in red
- Progress spinner shown during execution

## Key Files

- `src/resume_operator/main.py`
- `src/resume_operator/graph.py`

## Dependencies

- #006

## Implementation Details

### CLI command (`src/resume_operator/main.py`)

- Validates `resume.exists()` and `resume.is_file()` before invoking the graph
- Invokes `build_graph().invoke({"resume_path": str(resume)})` — full pipeline, stub nodes 2-6 are no-ops
- Rich `Status` spinner wraps the graph invocation for user feedback
- Errors from `result["errors"]` printed in `[red]` with `typer.Exit(code=1)`
- Displays: name, email, phone, skills (comma-joined), experience/education/certifications entry counts

### Bug fix: null coercion in parse_resume node (`src/resume_operator/nodes/parse_resume.py`)

- LLMs may return `null` for optional fields (e.g., `"phone": null`)
- `dict.get("phone", "")` only returns `""` when the key is missing, not when value is `null`
- Changed all field accessors from `parsed.get("field", "")` to `parsed.get("field") or ""` to coerce `None` to defaults
- Added `test_handles_null_fields_from_llm` test to cover this case

### Logging rule (`.claude/rules/logging.md`)

- Established logging conventions for all nodes and tools
- Node logging pattern: entry/exit at INFO, errors at ERROR, prompts/responses at DEBUG only
- CLI `--verbose` flag design: WARNING by default, DEBUG when verbose
- Security: no PII or API keys at INFO level
- Added rule reference in `.claude/CLAUDE.md`

### Tests (`tests/test_main.py`)

- 5 CLI tests using `typer.testing.CliRunner` with mocked `build_graph`:
  - `test_file_not_found` — nonexistent path exits 1
  - `test_not_a_file` — directory path exits 1
  - `test_successful_parse` — displays name, email, skills, counts
  - `test_pipeline_errors` — shows errors in output, exits 1
  - `test_resume_option_required` — missing `--resume` shows error

### Tests (`tests/test_parse_resume.py`)

- Added `test_handles_null_fields_from_llm` — verifies null coercion for all fields

## Labels

`enhancement`, `priority:medium`
