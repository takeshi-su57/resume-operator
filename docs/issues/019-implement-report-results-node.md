# [Feature]: Implement report_results node

## Description

Implement the final pipeline node that compiles all results into a JSON report and writes it to `data/results.json`. This node summarizes the full pipeline run including scores, changes, and any errors.

## Motivation

The JSON report provides a machine-readable summary of what the optimizer did. It's useful for reviewing changes, comparing runs, and debugging pipeline issues.

## Tasks

- [ ] Build a report dict from state: original resume path, job description, ATS score, gap analysis, optimization changes, output path, errors, timestamp
- [ ] Write the report to `data/results.json` using `json.dump` with indent=2
- [ ] Ensure `data/` directory is created if missing
- [ ] Return `{"report": report_dict}`
- [ ] Use `datetime.now().isoformat()` for timestamp

## Acceptance Criteria

- `data/results.json` is written with complete pipeline results
- Report includes: ats_score, gaps, changes_made, errors, output_path, timestamp
- Directory created if missing

## Key Files

- `src/resume_operator/nodes/report_results.py`

## Dependencies

- #014

## Labels

`enhancement`, `priority:high`
