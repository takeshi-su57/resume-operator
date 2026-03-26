# [Feature]: Implement PDF text extraction tool (pdf_parser.py)

## Description

The `tools/pdf_parser.py` stub raises `NotImplementedError`. Implement the `extract_text()` function using PyMuPDF (fitz) to open a PDF and concatenate text from all pages. This is pure I/O with no LLM involvement — a good first implementation task.

## Motivation

PDF parsing is the entry point of the entire pipeline. The resume must be converted from PDF to text before any LLM processing can happen. This is also the simplest tool to implement, building confidence with the codebase.

## Tasks

- [ ] Import `fitz` (PyMuPDF) in `tools/pdf_parser.py`
- [ ] Implement `extract_text(pdf_path: Path) -> str` — open PDF, iterate pages, extract text via `page.get_text()`, concatenate with newlines
- [ ] Add error handling: raise `FileNotFoundError` if path doesn't exist
- [ ] Add error handling: raise `ValueError` if PDF has no extractable text
- [ ] Verify `ruff check` and `mypy` pass

## Acceptance Criteria

- `extract_text()` returns concatenated text from all PDF pages
- `FileNotFoundError` raised for missing files
- `ValueError` raised for PDFs with empty text extraction
- Passes `ruff check` and `mypy`

## Key Files

- `src/resume_operator/tools/pdf_parser.py`

## Dependencies

- #001

## Labels

`enhancement`, `priority:high`
