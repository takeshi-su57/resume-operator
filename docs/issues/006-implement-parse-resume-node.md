# [Feature]: Implement and test parse_resume node

## Description

Implement the first pipeline node. `parse_resume` reads the resume PDF path from state, calls `tools/pdf_parser.py` to extract text, sends it to the LLM with the `prompts/resume_parsing.py` template, parses the JSON response, and returns a dict with the `resume` field populated. Also reads the job description from state text or file path. Unit tests cover happy path and all error paths with mocked LLM and PDF tools.

## Motivation

This is the entry point of the entire pipeline. Every subsequent node depends on the structured resume data produced here. It also establishes the implementation pattern (read state -> call tools -> call LLM -> parse response -> return delta) that all other nodes will follow. Testing it with mocks ensures the node pattern works before replicating it across all other nodes.

## LangGraph Concepts Introduced

- **Node function signature**: `(state: ResumeOptimizerState) -> dict`
- **State delta return**: return only the fields that changed, not the full state
- **LangGraph merges** the returned dict into the state automatically

## Tasks

### Implementation

- [x] Import `tools.pdf_parser.extract_text` and `tools.llm_provider.get_llm`
- [x] Import `prompts.resume_parsing.PARSE_RESUME` template
- [x] Read `state.resume_path`, call `extract_text()` to get raw text
- [x] Format the prompt template with the raw text
- [x] Call `get_llm().invoke()` with the formatted prompt
- [x] Parse the LLM JSON response (use `json.loads`)
- [x] Build `ResumeData` from parsed JSON, including `raw_text` field
- [x] Read `state.job_description_text` or fall back to reading `state.job_description_path` file
- [x] Return `{"resume": resume_data, "job_description": job_description}` (only changed fields)
- [x] Wrap in try/except — append errors to `state.errors` on failure (separate handlers for PDF, LLM, and JSON errors)

### Tests

- [x] Create `tests/test_parse_resume.py`
- [x] Mock `tools.pdf_parser.extract_text` to return sample resume text
- [x] Mock `tools.llm_provider.get_llm` to return a mock that returns valid JSON
- [x] Test: `test_parses_resume_successfully` — verify `ResumeData` fields populated, `raw_text` preserved, job description set
- [x] Test: `test_records_error_on_pdf_failure` — mock `extract_text` to raise `FileNotFoundError`, verify error in state, no `resume` key
- [x] Test: `test_records_error_on_llm_failure` — mock LLM to raise `RuntimeError`, verify error in state, no `resume` key
- [x] Test: `test_records_error_on_invalid_json` — mock LLM to return non-JSON string, verify error in state, no `resume` key
- [x] Test: `test_returns_only_changed_fields` — verify return dict keys are subset of `{resume, job_description, errors}`
- [x] Test: `test_reads_job_description_from_file` — verify job description read from file path when `job_description_text` is empty

## Acceptance Criteria

- [x] Node follows `(state) -> dict` signature returning only changed fields
- [x] Calls tools layer (not direct `fitz` or LLM imports)
- [x] Uses prompt template from `prompts/`, not inline strings
- [x] Errors are caught and recorded in `state.errors` with descriptive prefixes
- [x] All 6 tests pass with mocked tools, no real PDF files or API calls needed
- [x] Tests verify both happy path and error paths

## Implementation Details

### Error handling strategy

Three separate error paths, each returning early with errors appended:
1. **PDF extraction failure** — catches any exception from `extract_text()`, returns `{"errors": [...]}`
2. **LLM call failure** — catches `RuntimeError` or similar from `get_llm().invoke()`, returns `{"errors": [...]}`
3. **Invalid JSON** — catches `json.JSONDecodeError` when parsing LLM response, returns `{"errors": [...]}`

Job description file read errors are non-fatal — appended to errors but processing continues.

### Job description loading

Prefers `state.job_description_text` (inline text). Falls back to reading `state.job_description_path` as a file. Only populates `job_description` in the result if text was found.

## Key Files

- `src/resume_operator/nodes/parse_resume.py` (modified)
- `src/resume_operator/tools/pdf_parser.py` (dependency)
- `src/resume_operator/tools/llm_provider.py` (dependency)
- `src/resume_operator/prompts/resume_parsing.py` (dependency)
- `tests/test_parse_resume.py` (new — 6 tests)

## Dependencies

- #002 (pdf_parser), #004 (llm_provider)

## Labels

`enhancement`, `priority:high`
