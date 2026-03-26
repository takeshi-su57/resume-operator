# [Feature]: Implement and test generate_pdf node

## Description

Implement the node that calls `tools/pdf_generator.py` with the optimized resume sections from state and writes the output PDF. Then write unit tests with the pdf_generator tool mocked.

## Motivation

The generate_pdf node converts the LLM's optimized content into a tangible PDF file. Without this, the optimization is just data in memory — the user needs a file they can submit. Tests ensure the node calls the tools layer correctly and handles errors gracefully.

## Tasks

### Implementation

- [ ] Import `tools.pdf_generator.generate_pdf`
- [ ] Read `state.optimized_resume.sections` and `state.output_path`
- [ ] If `output_path` is empty, default to `data/optimized_resume.pdf`
- [ ] Call `generate_pdf(sections, Path(output_path))`
- [ ] Return `{"output_path": str(result_path)}`
- [ ] Error handling: catch exceptions, record in `state.errors`

### Tests

- [ ] Create `tests/test_generate_pdf_node.py`
- [ ] Mock `tools.pdf_generator.generate_pdf`, test node calls it correctly
- [ ] Test error handling when generator fails
- [ ] Test default output path when none specified

## Acceptance Criteria

- Node calls the tools layer, not ReportLab directly
- Default output path used when none specified
- Errors recorded, pipeline continues
- All tests pass with mocked tool layer

## Key Files

- `src/resume_operator/nodes/generate_pdf.py`
- `src/resume_operator/tools/pdf_generator.py`
- `tests/test_generate_pdf_node.py` (new)

## Dependencies

- #013

## Labels

`enhancement`, `priority:high`
