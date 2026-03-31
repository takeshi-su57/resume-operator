# [Chore]: Add LLM response parsing robustness (JSON extraction)

## Description

LLM responses sometimes include markdown code fences or extra text around JSON. Add a utility function that extracts JSON from LLM responses regardless of surrounding text. Use this in all LLM-calling nodes.

## Motivation

In practice, LLMs often wrap JSON in ```json ... ``` blocks or add explanatory text before/after. A robust JSON extractor prevents pipeline failures from minor LLM formatting inconsistencies.

## Tasks

- [x] Create `src/resume_operator/tools/json_parser.py` with `extract_json(text: str) -> dict[str, Any]`
- [x] Handle: raw JSON (direct `json.loads`), JSON wrapped in ````json ... ```` (regex for code fences), JSON with leading/trailing text (depth-counting brace matcher for first `{...}` block)
- [x] Use brace-depth matching to find the first balanced `{...}` block if `json.loads` and code-fence extraction both fail
- [x] Raise `ValueError` with descriptive message if no valid JSON object found (rejects arrays too)
- [x] Update all 4 LLM-calling nodes (`parse_resume`, `ats_score`, `analyze_gaps`, `optimize_content`) to use `extract_json()` instead of `json.loads()`, catch `ValueError` instead of `json.JSONDecodeError`, remove `import json`
- [x] Create `tests/test_json_parser.py` with 11 tests covering: raw JSON, whitespace, code-fenced (with/without language), text-wrapped, text before code fence, nested objects, braces in strings, invalid text, empty string, array rejection
- [x] Update `tests/test_graph.py` to mock all LLM-calling nodes properly (required because `extract_json` is more robust than `json.loads` and extracts JSON from mock responses that previously failed silently)

## Acceptance Criteria

- `extract_json()` handles code-fenced, raw, and text-wrapped JSON
- All LLM nodes use this utility
- Tests cover at least 5 input variations (raw, fenced, text-wrapped, nested, invalid)

## Key Files

- `src/resume_operator/tools/json_parser.py` (new)
- `tests/test_json_parser.py` (new)
- All files in `src/resume_operator/nodes/`

## Dependencies

- #012

## Labels

`chore`, `priority:medium`
