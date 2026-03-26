# [Feature]: Write unit tests for pdf_parser tool

## Description

Test the PDF parser tool implemented in #002. Create fixtures that generate small test PDFs using ReportLab (already a dependency) and verify `extract_text()` handles valid PDFs, missing files, and empty PDFs.

## Motivation

The PDF parser is the first external I/O tool — it must be reliable. Test-driven verification ensures edge cases (missing files, image-only PDFs, multi-page documents) are handled correctly.

## Tasks

- [x] Create `tests/test_pdf_parser.py`
- [x] Add a pytest fixture that generates a tiny PDF with known text using ReportLab (write to `tmp_path`)
- [x] Add a fixture that generates an image-only PDF (no extractable text)
- [x] Test: `test_extracts_text_from_valid_pdf` — verify known text is returned
- [x] Test: `test_raises_on_missing_file` — verify `FileNotFoundError`
- [x] Test: `test_raises_on_empty_text` — verify `ValueError` for image-only PDF
- [x] Test: `test_multipage_extraction` — verify text from multiple pages is concatenated

## Acceptance Criteria

- All tests pass with `pytest tests/test_pdf_parser.py`
- No external PDF files required (fixtures generate test PDFs)
- Tests follow project conventions: class-based, descriptive names

## Key Files

- `tests/test_pdf_parser.py` (new)
- `src/resume_operator/tools/pdf_parser.py`

## Dependencies

- #002

## Labels

`enhancement`, `priority:high`
