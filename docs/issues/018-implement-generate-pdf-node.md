# [Feature]: Implement generate_pdf node

## Description

Implement the node that calls `tools/pdf_generator.py` with the optimized resume sections from state and writes the output PDF. This node bridges the LLM optimization results to the final user-facing deliverable.

## Motivation

The generate_pdf node converts the LLM's optimized content into a tangible PDF file. Without this, the optimization is just data in memory — the user needs a file they can submit.

## Tasks

- [ ] Import `tools.pdf_generator.generate_pdf`
- [ ] Read `state.optimized_resume.sections` and `state.output_path`
- [ ] If `output_path` is empty, default to `data/optimized_resume.pdf`
- [ ] Call `generate_pdf(sections, Path(output_path))`
- [ ] Return `{"output_path": str(result_path)}`
- [ ] Error handling: catch exceptions, record in `state.errors`

## Acceptance Criteria

- Node calls the tools layer, not ReportLab directly
- Default output path used when none specified
- Errors recorded, pipeline continues

## Key Files

- `src/resume_operator/nodes/generate_pdf.py`
- `src/resume_operator/tools/pdf_generator.py`

## Dependencies

- #016

## Labels

`enhancement`, `priority:high`
