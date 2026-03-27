# [Chore]: Add LLM response parsing robustness (JSON extraction)

## Description

LLM responses sometimes include markdown code fences or extra text around JSON. Add a utility function that extracts JSON from LLM responses regardless of surrounding text. Use this in all LLM-calling nodes.

## Motivation

In practice, LLMs often wrap JSON in ```json ... ``` blocks or add explanatory text before/after. A robust JSON extractor prevents pipeline failures from minor LLM formatting inconsistencies.

## Tasks

- [ ] Create `src/resume_operator/tools/json_parser.py` with `extract_json(text: str) -> dict`
- [ ] Handle: raw JSON, JSON wrapped in ```json ... ```, JSON with leading/trailing text
- [ ] Use regex to find the first `{...}` block if `json.loads` fails on full text
- [ ] Raise `ValueError` with descriptive message if no valid JSON found
- [ ] Update all four LLM-calling nodes to use `extract_json()` instead of raw `json.loads()`
- [ ] Create `tests/test_json_parser.py` covering all parsing scenarios

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
