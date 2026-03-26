"""LangChain model factory — returns a BaseChatModel based on config."""

from langchain_core.language_models import BaseChatModel

from resume_operator.config import get_settings


def get_llm() -> BaseChatModel:
    """Return a LangChain chat model based on LLM_PROVIDER env var.

    Supports: openai, anthropic, google.
    Provider-specific packages are imported lazily.
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=settings.llm_model, api_key=settings.anthropic_api_key)
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=settings.llm_model, api_key=settings.google_api_key)
    else:
        msg = f"Unsupported LLM provider: {provider}"
        raise ValueError(msg)
