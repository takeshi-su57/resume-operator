"""LangChain model factory — returns a BaseChatModel based on config."""

import logging

from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from resume_operator.config import get_settings

logger = logging.getLogger(__name__)

# Maps provider name to (Settings attribute, environment variable name).
_PROVIDER_KEY_MAP: dict[str, tuple[str, str]] = {
    "openai": ("openai_api_key", "OPENAI_API_KEY"),
    "anthropic": ("anthropic_api_key", "ANTHROPIC_API_KEY"),
    "google": ("google_api_key", "GOOGLE_API_KEY"),
    "openrouter": ("openrouter_api_key", "OPENROUTER_API_KEY"),
}


def get_llm(
    provider: str | None = None,
    model: str | None = None,
) -> BaseChatModel:
    """Return a LangChain chat model based on LLM_PROVIDER env var.

    Supports: openai, anthropic, google, openrouter.
    Provider-specific packages are imported lazily.

    Args:
        provider: Override the configured LLM_PROVIDER.
        model: Override the configured LLM_MODEL.
    """
    settings = get_settings()
    resolved_provider = (provider or settings.llm_provider).lower()
    resolved_model = model or settings.llm_model

    # Validate provider is supported and API key is present.
    if resolved_provider not in _PROVIDER_KEY_MAP:
        msg = f"Unsupported LLM provider: {resolved_provider}"
        raise ValueError(msg)

    attr_name, env_var = _PROVIDER_KEY_MAP[resolved_provider]
    api_key: str = getattr(settings, attr_name)
    if not api_key:
        msg = f"{env_var} not set. Add it to your .env file."
        raise ValueError(msg)

    logger.info("LLM provider: provider=%s, model=%s", resolved_provider, resolved_model)

    if resolved_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=resolved_model, api_key=SecretStr(api_key))
    elif resolved_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(  # type: ignore[call-arg]
            model_name=resolved_model, api_key=SecretStr(api_key)
        )
    elif resolved_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=resolved_model, api_key=api_key)
    else:  # openrouter
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=resolved_model,
            api_key=SecretStr(api_key),
            base_url="https://openrouter.ai/api/v1",
        )
