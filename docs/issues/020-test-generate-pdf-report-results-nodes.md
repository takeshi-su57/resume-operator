# [Feature]: Write unit tests for generate_pdf and report_results nodes

## Description

Test the final two pipeline nodes. Mock the pdf_generator tool for the generate_pdf node, and verify report_results writes correct JSON output.

## Motivation

These nodes produce the user-facing output (PDF file and JSON report). Tests ensure the output is complete, correctly formatted, and handles missing data gracefully.

## Tasks

- [ ] Create `tests/test_generate_pdf_node.py`
- [ ] Mock `tools.pdf_generator.generate_pdf`, test node calls it correctly
- [ ] Test error handling when generator fails
- [ ] Test default output path when none specified
- [ ] Create `tests/test_report_results.py`
- [ ] Test: `test_writes_json_report` — use `tmp_path`, verify JSON written and parseable
- [ ] Test: `test_report_contains_all_fields` — verify timestamp, ats_score, gaps, etc.
- [ ] Test: `test_creates_data_directory` — verify dir creation

## Acceptance Criteria

- All tests pass
- report_results tests use `tmp_path` (not real `data/` directory)
- generate_pdf node tests mock the tool layer

## Key Files

- `tests/test_generate_pdf_node.py` (new)
- `tests/test_report_results.py` (new)

## Dependencies

- #018, #019

## Labels

`enhancement`, `priority:high`
