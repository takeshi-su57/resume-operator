# [Feature]: Implement LLM provider factory with validation (llm_provider.py)

## Description

The `tools/llm_provider.py` has a basic implementation but lacks input validation. Enhance it to validate that the API key is non-empty for the selected provider before constructing the model, and add helpful error messages guiding users to set their `.env` file.

## Motivation

Four of six pipeline nodes depend on the LLM provider. A clear error when the API key is missing saves significant debugging time — especially for users setting up the project for the first time.

## Tasks

- [ ] Add validation: if the API key for the selected provider is empty, raise `ValueError` with a message like `"OPENAI_API_KEY not set. Add it to your .env file."`
- [ ] Add optional `provider`/`model` parameters to `get_llm()` that override settings (useful for testing)
- [ ] Ensure `mypy` passes with strict mode
- [ ] Verify all three provider paths work (OpenAI, Anthropic, Google)

## Acceptance Criteria

- `get_llm()` raises `ValueError` with helpful message when API key is missing
- Optional `provider`/`model` parameters override settings
- `mypy` strict mode passes

## Key Files

- `src/resume_operator/tools/llm_provider.py`
- `src/resume_operator/config.py`

## Dependencies

- #001

## Labels

`enhancement`, `priority:high`
