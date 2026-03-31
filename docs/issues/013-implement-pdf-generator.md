# [Feature]: Implement and test PDF generation tool (pdf_generator.py)

## Description

Implement the ReportLab-based PDF generator that takes optimized resume sections and renders them into a formatted PDF. Then write unit tests that verify valid PDFs are produced with expected content. This is a tools-layer task with no LLM involvement.

## Motivation

The final deliverable is a PDF resume the user can submit. ReportLab gives full control over layout, fonts, and formatting — essential for producing a professional-looking resume. Tests must verify the output is a valid PDF containing the expected content — not just that a file was written.

## Tasks

### Implementation

- [x] Import `reportlab` modules (`SimpleDocTemplate`, `Paragraph`, `Spacer`, styles)
- [x] Implement `generate_pdf(sections: dict[str, str], output_path: Path) -> Path`
- [x] Create a clean resume layout: name/header area, then sections in order (summary, experience, skills, education)
- [x] Use ReportLab paragraph styles for section headers and body text
- [x] Ensure `output_path` parent directory is created if it doesn't exist
- [x] Return the output path on success
- [x] Raise `ValueError` if `sections` is empty
- [x] XML-escape section content via `xml.sax.saxutils.escape()` to handle `&`, `<`, `>` safely
- [x] Handle multi-paragraph content (`\n\n` splits) and line breaks (`\n` → `<br/>`)
- [x] Add `reportlab.*` to mypy overrides in `pyproject.toml`

### Tests

- [x] Create `tests/test_pdf_generator.py`
- [x] Test: `test_generates_pdf_from_sections` — pass sample sections, verify output file exists and is valid PDF (checks `%PDF` magic bytes)
- [x] Test: `test_raises_on_empty_sections` — verify `ValueError`
- [x] Test: `test_creates_parent_directories` — pass nested path in `tmp_path`, verify dirs created
- [x] Test: `test_pdf_contains_section_text` — generate PDF, re-parse with PyMuPDF, verify section headers and body text present
- [x] Test: `test_returns_output_path` — verify return value matches provided path

## Acceptance Criteria

- Generates a readable PDF from sections dict
- Creates parent directories as needed
- Raises `ValueError` for empty sections
- Output PDF opens in a PDF viewer without errors
- All tests pass, generated PDFs verified by re-parsing with PyMuPDF
- Uses `tmp_path` fixture for output (no leftover files)

## Key Files

- `src/resume_operator/tools/pdf_generator.py`
- `tests/test_pdf_generator.py` (new)

## Dependencies

- #001

## Labels

`enhancement`, `priority:high`
