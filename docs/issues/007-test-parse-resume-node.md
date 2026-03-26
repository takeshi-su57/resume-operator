# [Feature]: Write unit tests for parse_resume node

## Description

Test the `parse_resume` node with mocked LLM and PDF tools. Verify it correctly processes LLM responses, handles errors gracefully, and returns the expected state delta.

## Motivation

As the first node, `parse_resume` sets the quality bar. Testing it with mocks ensures the node pattern works before replicating it across all other nodes.

## Tasks

- [ ] Create `tests/test_parse_resume.py`
- [ ] Mock `tools.pdf_parser.extract_text` to return sample resume text
- [ ] Mock `tools.llm_provider.get_llm` to return a mock that returns valid JSON
- [ ] Test: `test_parses_resume_successfully` — verify `ResumeData` fields populated
- [ ] Test: `test_records_error_on_pdf_failure` — mock `extract_text` to raise, verify error in state
- [ ] Test: `test_records_error_on_llm_failure` — mock LLM to raise, verify error in state
- [ ] Test: `test_records_error_on_invalid_json` — mock LLM to return garbage, verify error in state
- [ ] Test: `test_returns_only_changed_fields` — verify return dict has only expected keys

## Acceptance Criteria

- All tests pass with mocked tools
- No real PDF files or API calls needed
- Tests verify both happy path and error paths

## Key Files

- `tests/test_parse_resume.py` (new)
- `src/resume_operator/nodes/parse_resume.py`

## Dependencies

- #006

## Labels

`enhancement`, `priority:high`
