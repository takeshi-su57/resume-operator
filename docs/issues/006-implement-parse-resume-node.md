# [Feature]: Implement parse_resume node

## Description

Implement the first pipeline node. `parse_resume` reads the resume PDF path from state, calls `tools/pdf_parser.py` to extract text, sends it to the LLM with the `prompts/resume_parsing.py` template, parses the JSON response, and returns a dict with the `resume` field populated. This is the first encounter with the LangGraph node pattern.

## Motivation

This is the entry point of the entire pipeline. Every subsequent node depends on the structured resume data produced here. It also establishes the implementation pattern (read state → call tools → call LLM → parse response → return delta) that all other nodes will follow.

## LangGraph Concepts Introduced

- **Node function signature**: `(state: ResumeOptimizerState) -> dict`
- **State delta return**: return only the fields that changed, not the full state
- **LangGraph merges** the returned dict into the state automatically

## Tasks

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

## Acceptance Criteria

- Node follows `(state) -> dict` signature returning only changed fields
- Calls tools layer (not direct `fitz` or LLM imports)
- Uses prompt template from `prompts/`, not inline strings
- Errors are caught and recorded in `state.errors`

## Key Files

- `src/resume_operator/nodes/parse_resume.py`
- `src/resume_operator/tools/pdf_parser.py`
- `src/resume_operator/tools/llm_provider.py`
- `src/resume_operator/prompts/resume_parsing.py`

## Dependencies

- #002, #004

## Labels

`enhancement`, `priority:high`
