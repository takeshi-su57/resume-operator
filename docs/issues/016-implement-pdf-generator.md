# [Feature]: Implement PDF generation tool (pdf_generator.py)

## Description

Implement the ReportLab-based PDF generator that takes optimized resume sections and renders them into a formatted PDF. This is a tools-layer task with no LLM involvement.

## Motivation

The final deliverable is a PDF resume the user can submit. ReportLab gives full control over layout, fonts, and formatting — essential for producing a professional-looking resume.

## Tasks

- [ ] Import `reportlab` modules (`SimpleDocTemplate`, `Paragraph`, `Spacer`, styles)
- [ ] Implement `generate_pdf(sections: dict[str, str], output_path: Path) -> Path`
- [ ] Create a clean resume layout: name/header area, then sections in order (summary, experience, skills, education)
- [ ] Use ReportLab paragraph styles for section headers and body text
- [ ] Ensure `output_path` parent directory is created if it doesn't exist
- [ ] Return the output path on success
- [ ] Raise `ValueError` if `sections` is empty

## Acceptance Criteria

- Generates a readable PDF from sections dict
- Creates parent directories as needed
- Raises `ValueError` for empty sections
- Output PDF opens in a PDF viewer without errors

## Key Files

- `src/resume_operator/tools/pdf_generator.py`

## Dependencies

- #001

## Labels

`enhancement`, `priority:high`
