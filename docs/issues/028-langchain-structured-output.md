# [Refactor]: Replace manual `extract_json` with LangChain `with_structured_output`

## Description

All four LLM-calling nodes (`parse_resume`, `ats_score`, `analyze_gaps`, `optimize_content`) previously asked the LLM for JSON in the prompt, received a string, and passed it through `tools/json_parser.py`'s `extract_json`. This migration replaces that pattern with LangChain's `model.with_structured_output(PydanticModel)`, which uses provider-native function-calling / tool-use for reliable schema adherence.

## Motivation

Manual JSON parsing fails regularly — markdown fences, prose wrapping, malformed JSON, escaped quotes, unicode noise. Each node had a `ValueError` handler for this. `with_structured_output` eliminates the parse step entirely: the model returns an already-validated Pydantic instance. Fewer failure modes, tighter prompts (the schema replaces "return ONLY valid JSON" boilerplate), and schema validation happens at the SDK boundary.

## Implementation

- [x] `get_structured_llm(schema)` helper added to [`tools/llm_provider.py`](../../src/resume_operator/tools/llm_provector.py) — returns `llm.with_structured_output(schema)`
- [x] Per-node `…LLMOutput` Pydantic schemas defined alongside each node function:
  - `ResumeLLMOutput` + `ResumeExperienceLLM` + `ResumeEducationLLM` in [parse_resume.py](../../src/resume_operator/nodes/parse_resume.py)
  - `ATSScoreLLMOutput` in [ats_score.py](../../src/resume_operator/nodes/ats_score.py)
  - `GapAnalysisLLMOutput` in [analyze_gaps.py](../../src/resume_operator/nodes/analyze_gaps.py)
  - `OptimizedResumeLLMOutput` + `OptimizedSections` in [optimize_content.py](../../src/resume_operator/nodes/optimize_content.py)
- [x] All four nodes migrated — no node calls `extract_json` on its happy path
- [x] "Return ONLY valid JSON" boilerplate stripped from [all four prompt files](../../src/resume_operator/prompts/)
- [x] `tools/json_parser.py` + its test deleted (no fallback path needed — providers either support structured output or aren't appropriate for this pipeline)
- [x] Tests rewritten to patch `get_structured_llm` and return Pydantic instances directly instead of mocking `.content` JSON strings
- [x] `.env.example` documents per-provider model compatibility notes

## Per-Provider Behavior — Verified

| Provider | Method | Status | Notes |
|----------|--------|--------|-------|
| OpenAI (gpt-4o, gpt-4o-mini) | `json_schema` (strict) | Works | Default behavior. Schemas must have all properties in `required`, which is why `OptimizedResumeLLMOutput.sections` uses a fixed `OptimizedSections` sub-model instead of an open `dict[str, str]`. |
| Anthropic (Claude 3.5) | tool-use | Expected to work | Untested in this PR; LangChain uses Anthropic's tool-use API. |
| Google (Gemini 1.5) | function-calling | Partial | LangChain supports it, but some default-field behavior differs — untested in this PR. |
| OpenRouter + OpenAI-origin models (e.g. `openai/gpt-4o-mini`) | OpenAI-compatible JSON schema | Works | Real-run verified end-to-end. |
| OpenRouter + open-weights (e.g. `openai/gpt-oss-120b`) | OpenAI-compatible JSON schema | Broken | Returns truncated JSON that fails Pydantic validation. Document-and-skip — use a different model. |

## Schema Design Notes

OpenAI's strict JSON schema mode requires every property in `properties` to also be in `required`, and it does not accept open-ended `dict[str, str]` fields. Two schemas needed adjustment:

1. `OptimizedResumeLLMOutput.sections` — was `dict[str, str]`, now `OptimizedSections` with fixed fields (`summary`, `experience`, `skills`, `education`).
2. `ResumeLLMOutput.experience` / `.education` — was `list[dict[str, str]]`, now `list[ResumeExperienceLLM]` / `list[ResumeEducationLLM]` with fixed fields.

The state model (`ResumeData`, `OptimizedResume`) still uses the open shapes — the node converts between LLM schema and state at the boundary.

## Acceptance Criteria — Verified

- No node calls `extract_json` on its happy path ✓ (file deleted)
- Prompts no longer contain JSON-formatting boilerplate ✓ (all four prompts rewritten)
- Schema mismatches surface via the existing "record error, continue" pattern ✓ (`ValidationError` and generic `Exception` handlers)
- Real-run proof: `run --master … --facts … --job …` with `LLM_MODEL=openai/gpt-4o-mini` completes all four LLM-calling nodes with no errors — score 0.73, optimization produced 4 sections and 5 changes, tailored PDF written clean

## Key Files

- `src/resume_operator/tools/llm_provider.py`
- `src/resume_operator/nodes/{parse_resume,ats_score,analyze_gaps,optimize_content}.py`
- `src/resume_operator/prompts/*.py`
- `src/resume_operator/tools/json_parser.py` (deleted)
- `tests/test_{parse_resume,ats_score,analyze_gaps,optimize_content,integration,graph}.py`
- `.env.example`
- `docs/architecture.md`

## Labels

`refactor`, `priority:medium`
