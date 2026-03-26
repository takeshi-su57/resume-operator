# [Feature]: Write unit tests for llm_provider and config

## Description

Test the LLM provider factory and config module. Mock environment variables and LangChain constructors to verify correct provider selection, API key validation, and settings loading. No real API calls are made.

## Motivation

The LLM provider is used by four nodes. Testing it with mocks ensures provider switching works correctly and that clear errors appear for missing keys — before any LLM-dependent code is written.

## Tasks

- [ ] Create `tests/test_llm_provider.py`
- [ ] Test: `test_returns_openai_model` — mock env vars + `ChatOpenAI`, verify it's called
- [ ] Test: `test_returns_anthropic_model` — same for Anthropic
- [ ] Test: `test_returns_google_model` — same for Google
- [ ] Test: `test_raises_on_unsupported_provider` — verify `ValueError`
- [ ] Test: `test_raises_on_missing_api_key` — verify `ValueError` with helpful message
- [ ] Create `tests/test_config.py`
- [ ] Test: `test_default_settings` — verify defaults match `.env.example`
- [ ] Test: `test_settings_from_env` — mock env vars and verify settings load

## Acceptance Criteria

- All tests pass, no real API calls made
- LLM constructors are mocked (no API keys needed)
- Config tests use `@patch.dict("os.environ", ...)` pattern

## Key Files

- `tests/test_llm_provider.py` (new)
- `tests/test_config.py` (new)
- `src/resume_operator/tools/llm_provider.py`
- `src/resume_operator/config.py`

## Dependencies

- #004

## Labels

`enhancement`, `priority:high`
