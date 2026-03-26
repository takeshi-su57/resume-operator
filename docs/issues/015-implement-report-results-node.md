# [Feature]: Implement and test report_results node

## Description

Implement the final pipeline node that compiles all results into a JSON report and writes it to `data/results.json`. Then write unit tests verifying the JSON output is complete and correctly formatted.

## Motivation

The JSON report provides a machine-readable summary of what the optimizer did. It's useful for reviewing changes, comparing runs, and debugging pipeline issues. Tests ensure the output is complete and handles missing data gracefully.

## Tasks

### Implementation

- [ ] Build a report dict from state: original resume path, job description, ATS score, gap analysis, optimization changes, output path, errors, timestamp
- [ ] Write the report to `data/results.json` using `json.dump` with indent=2
- [ ] Ensure `data/` directory is created if missing
- [ ] Return `{"report": report_dict}`
- [ ] Use `datetime.now().isoformat()` for timestamp

### Tests

- [ ] Create `tests/test_report_results.py`
- [ ] Test: `test_writes_json_report` — use `tmp_path`, verify JSON written and parseable
- [ ] Test: `test_report_contains_all_fields` — verify timestamp, ats_score, gaps, etc.
- [ ] Test: `test_creates_data_directory` — verify dir creation

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
