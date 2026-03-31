# [Feature]: Implement and test generate_pdf node

## Description

Implement the node that calls `tools/pdf_generator.py` with the optimized resume sections from state and writes the output PDF. Then write unit tests with the pdf_generator tool mocked.

## Motivation

The generate_pdf node converts the LLM's optimized content into a tangible PDF file. Without this, the optimization is just data in memory — the user needs a file they can submit. Tests ensure the node calls the tools layer correctly and handles errors gracefully.

## Tasks

### Implementation

- [x] Import `tools.pdf_generator.generate_pdf` (aliased as `create_pdf` to avoid name collision with node function)
- [x] Read `state.optimized_resume.sections` and `state.output_path`
- [x] If `output_path` is empty, default to `data/optimized_resume.pdf`
- [x] Call `generate_pdf(sections, Path(output_path))`
- [x] Return `{"output_path": str(result_path)}`
- [x] Error handling: catch exceptions, record in `state.errors`
- [x] Logging: INFO at node start/completion (with output path and file size), ERROR on failure

### Tests

- [x] Create `tests/test_generate_pdf.py` (named to match project convention: `test_<module>.py`)
- [x] Mock `tools.pdf_generator.generate_pdf`, test node calls it with correct sections and path
- [x] Test error handling when generator fails (errors recorded, no output_path returned)
- [x] Test default output path when none specified
- [x] Test returns only changed fields (output_path, optionally errors)
- [x] Test preserves existing errors when new error occurs
- [x] Test errors key omitted on success

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
