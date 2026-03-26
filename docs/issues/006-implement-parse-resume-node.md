# [Feature]: Implement and test parse_resume node

## Description

Implement the first pipeline node. `parse_resume` reads the resume PDF path from state, calls `tools/pdf_parser.py` to extract text, sends it to the LLM with the `prompts/resume_parsing.py` template, parses the JSON response, and returns a dict with the `resume` field populated. Then write unit tests with mocked LLM and PDF tools.

## Motivation

This is the entry point of the entire pipeline. Every subsequent node depends on the structured resume data produced here. It also establishes the implementation pattern (read state -> call tools -> call LLM -> parse response -> return delta) that all other nodes will follow. Testing it with mocks ensures the node pattern works before replicating it across all other nodes.

## LangGraph Concepts Introduced

- **Node function signature**: `(state: ResumeOptimizerState) -> dict`
- **State delta return**: return only the fields that changed, not the full state
- **LangGraph merges** the returned dict into the state automatically

## Tasks

### Implementation

- [ ] Import `tools.pdf_parser.extract_text` and `tools.llm_provider.get_llm`
- [ ] Import `prompts.resume_parsing.PARSE_RESUME` template
- [ ] Read `state.resume_path`, call `extract_text()` to get raw text
- [ ] Format the prompt template with the raw text
- [ ] Call `get_llm().invoke()` with the formatted prompt
- [ ] Parse the LLM JSON response (use `json.loads`)
- [ ] Build `ResumeData` from parsed JSON, including `raw_text` field
- [ ] Also read `state.job_description_path` or `state.job_description_text` and populate `job_description.raw_text`
- [ ] Return `{"resume": resume_data, "job_description": job_description}`
- [ ] Wrap in try/except — append errors to `state.errors` on failure

### Tests

- [ ] Create `tests/test_parse_resume.py`
- [ ] Mock `tools.pdf_parser.extract_text` to return sample resume text
- [ ] Mock `tools.llm_provider.get_llm` to return a mock that returns valid JSON
- [ ] Test: `test_parses_resume_successfully` — verify `ResumeData` fields populated
- [ ] Test: `test_records_error_on_pdf_failure` — mock `extract_text` to raise, verify error in state
- [ ] Test: `test_records_error_on_llm_failure` — mock LLM to raise, verify error in state
- [ ] Test: `test_records_error_on_invalid_json` — mock LLM to return garbage, verify error in state
- [ ] Test: `test_returns_only_changed_fields` — verify return dict has only expected keys

## Acceptance Criteria

- Node follows `(state) -> dict` signature returning only changed fields
- Calls tools layer (not direct `fitz` or LLM imports)
- Uses prompt template from `prompts/`, not inline strings
- Errors are caught and recorded in `state.errors`
- All tests pass with mocked tools, no real PDF files or API calls needed
- Tests verify both happy path and error paths

## Key Files

- `src/resume_operator/nodes/parse_resume.py`
- `src/resume_operator/tools/pdf_parser.py`
- `src/resume_operator/tools/llm_provider.py`
- `src/resume_operator/prompts/resume_parsing.py`
- `tests/test_parse_resume.py` (new)

## Dependencies

- #002, #004

## Labels

`enhancement`, `priority:high`
