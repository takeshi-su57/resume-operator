# [Feature]: Implement and test report_results node

## Description

Implement the final pipeline node that compiles all results into a JSON report and writes it to `data/results.json`. Then write unit tests verifying the JSON output is complete and correctly formatted.

## Motivation

The JSON report provides a machine-readable summary of what the optimizer did. It's useful for reviewing changes, comparing runs, and debugging pipeline issues. Tests ensure the output is complete and handles missing data gracefully.

## Tasks

### Implementation

- [x] Build a report dict from state: resume_path, job_description_path, ATS score (`model_dump()`), gap analysis (`model_dump()`), optimization changes, output path, errors, timestamp
- [x] Write the report to `data/results.json` using `json.dump` with indent=2
- [x] Ensure `data/` directory is created if missing (`mkdir(parents=True, exist_ok=True)`)
- [x] Return `{"report": report_dict}`
- [x] Use `datetime.now().isoformat()` for timestamp
- [x] Error handling: catch exceptions, record in `state.errors`, return early
- [x] Logging: INFO at node start/completion (with output path), ERROR on failure
- [x] Defined `RESULTS_PATH = Path("data/results.json")` as patchable module constant for testability

### Tests

- [x] Create `tests/test_report_results.py`
- [x] Test: `test_writes_json_report` — use `tmp_path`, verify JSON written and parseable
- [x] Test: `test_report_contains_all_fields` — verify all 8 keys, validate timestamp is ISO format, check ats_score.score matches fixture
- [x] Test: `test_creates_data_directory` — verify nested dir creation
- [x] Test: `test_handles_write_error` — mock PermissionError, verify error recorded, no report returned
- [x] Test: `test_preserves_existing_errors` — pre-existing errors kept when new error occurs
- [x] Test: `test_returns_only_changed_fields` — result keys subset of {report, errors}

## Acceptance Criteria

- `data/results.json` is written with complete pipeline results
- Report includes: ats_score, gaps, changes_made, errors, output_path, timestamp
- Directory created if missing
- All tests pass, uses `tmp_path` (not real `data/` directory)

## Key Files

- `src/resume_operator/nodes/report_results.py`
- `tests/test_report_results.py` (new)

## Dependencies

- #012

## Labels

`enhancement`, `priority:high`
