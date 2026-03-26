# [Feature]: Write unit tests for pdf_generator tool

## Description

Test the PDF generator. Verify it creates valid PDFs, handles edge cases, and produces readable output. Use PyMuPDF to re-parse generated PDFs and verify content.

## Motivation

The PDF is the user-facing output. Tests must verify it's a valid PDF and contains the expected content — not just that a file was written.

## Tasks

- [ ] Create `tests/test_pdf_generator.py`
- [ ] Test: `test_generates_pdf_from_sections` — pass sample sections, verify output file exists and is valid PDF
- [ ] Test: `test_raises_on_empty_sections` — verify `ValueError`
- [ ] Test: `test_creates_parent_directories` — pass nested path in `tmp_path`, verify dirs created
- [ ] Test: `test_pdf_contains_section_text` — generate PDF, re-parse with PyMuPDF, verify text present
- [ ] Test: `test_returns_output_path` — verify return value matches provided path

## Acceptance Criteria

- All tests pass
- Generated PDFs verified by re-parsing with PyMuPDF
- Uses `tmp_path` fixture for output (no leftover files)

## Key Files

- `tests/test_pdf_generator.py` (new)
- `src/resume_operator/tools/pdf_generator.py`

## Dependencies

- #016

## Labels

`enhancement`, `priority:high`
