# [Feature]: Write unit tests for llm_provider and config

## Description

Test the LLM provider factory and config module. Mock environment variables and LangChain constructors to verify correct provider selection, API key validation, and settings loading. No real API calls are made.

## Motivation

The LLM provider is used by four nodes. Testing it with mocks ensures provider switching works correctly and that clear errors appear for missing keys — before any LLM-dependent code is written.

## Tasks

### `tests/test_llm_provider.py`

- [x] Create `tests/test_llm_provider.py`
- [x] `TestApiKeyValidation::test_raises_when_openai_key_missing` — mock settings, verify `ValueError` with "OPENAI_API_KEY not set"
- [x] `TestApiKeyValidation::test_raises_when_anthropic_key_missing` — same for Anthropic
- [x] `TestApiKeyValidation::test_raises_when_google_key_missing` — same for Google
- [x] `TestApiKeyValidation::test_raises_when_openrouter_key_missing` — same for OpenRouter
- [x] `TestApiKeyValidation::test_raises_on_unsupported_provider` — verify `ValueError` with "Unsupported LLM provider"
- [x] `TestProviderModelOverrides::test_provider_override_selects_correct_path` — `provider` param overrides settings
- [x] `TestProviderModelOverrides::test_model_override` — `model` param overrides settings
- [x] `TestProviderConstruction::test_openai_path` — mock `ChatOpenAI`, verify it's called
- [x] `TestProviderConstruction::test_anthropic_path` — mock `ChatAnthropic`, verify it's called
- [x] `TestProviderConstruction::test_google_path` — mock `ChatGoogleGenerativeAI`, verify it's called
- [x] `TestProviderConstruction::test_openrouter_path` — mock `ChatOpenAI`, verify `base_url` is set

### `tests/test_config.py`

- [x] Create `tests/test_config.py`
- [x] `TestDefaultSettings::test_default_llm_provider` — verify default is `"openai"`
- [x] `TestDefaultSettings::test_default_llm_model` — verify default is `"gpt-4o"`
- [x] `TestDefaultSettings::test_default_api_keys_empty` — verify all API keys default to `""`
- [x] `TestDefaultSettings::test_default_log_level` — verify default is `"INFO"`
- [x] `TestSettingsFromEnv::test_settings_from_env` — mock Anthropic env vars, verify settings load
- [x] `TestSettingsFromEnv::test_google_provider_from_env` — mock Google env vars
- [x] `TestSettingsFromEnv::test_single_key_from_env` — mock single key, verify others remain default

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
