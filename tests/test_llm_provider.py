"""Tests for LLM provider factory."""

from unittest.mock import MagicMock, patch

import pytest

from resume_operator.tools.llm_provider import get_llm


def _make_settings(**overrides: str) -> MagicMock:
    """Create a mock Settings with sensible defaults and optional overrides."""
    defaults = {
        "llm_provider": "openai",
        "llm_model": "gpt-4o",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "google_api_key": "",
        "openrouter_api_key": "",
    }
    defaults.update(overrides)
    settings = MagicMock()
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


class TestApiKeyValidation:
    """get_llm() must raise ValueError when the API key is missing."""

    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_raises_when_openai_key_missing(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value = _make_settings(llm_provider="openai")
        with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
            get_llm()

    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_raises_when_anthropic_key_missing(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value = _make_settings(llm_provider="anthropic")
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not set"):
            get_llm()

    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_raises_when_google_key_missing(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value = _make_settings(llm_provider="google")
        with pytest.raises(ValueError, match="GOOGLE_API_KEY not set"):
            get_llm()

    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_raises_when_openrouter_key_missing(self, mock_gs: MagicMock) -> None:
        mock_gs.return_value = _make_settings(llm_provider="openrouter")
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY not set"):
            get_llm()

    def test_raises_on_unsupported_provider(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM provider: fakellm"):
            get_llm(provider="fakellm")


class TestProviderModelOverrides:
    """Optional provider/model parameters override settings."""

    @patch("langchain_openai.ChatOpenAI", create=True)
    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_provider_override_selects_correct_path(
        self, mock_gs: MagicMock, mock_cls: MagicMock
    ) -> None:
        """provider='openai' uses OpenAI path even if settings say anthropic."""
        mock_gs.return_value = _make_settings(llm_provider="anthropic", openai_api_key="sk-test")
        mock_cls.return_value = MagicMock()
        get_llm(provider="openai")
        mock_cls.assert_called_once()

    @patch("langchain_openai.ChatOpenAI", create=True)
    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_model_override(self, mock_gs: MagicMock, mock_cls: MagicMock) -> None:
        mock_gs.return_value = _make_settings(openai_api_key="sk-test")
        mock_cls.return_value = MagicMock()
        get_llm(model="gpt-3.5-turbo")
        call_kwargs = mock_cls.call_args
        assert call_kwargs is not None
        assert str(call_kwargs[1]["model"]) == "gpt-3.5-turbo"


class TestProviderConstruction:
    """Each provider path constructs the correct LangChain class."""

    @patch("langchain_openai.ChatOpenAI", create=True)
    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_openai_path(self, mock_gs: MagicMock, mock_cls: MagicMock) -> None:
        mock_gs.return_value = _make_settings(openai_api_key="sk-test")
        mock_cls.return_value = MagicMock()
        get_llm()
        mock_cls.assert_called_once()

    @patch("langchain_anthropic.ChatAnthropic", create=True)
    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_anthropic_path(self, mock_gs: MagicMock, mock_cls: MagicMock) -> None:
        mock_gs.return_value = _make_settings(
            llm_provider="anthropic", anthropic_api_key="sk-ant-test"
        )
        mock_cls.return_value = MagicMock()
        get_llm()
        mock_cls.assert_called_once()

    @patch("langchain_google_genai.ChatGoogleGenerativeAI", create=True)
    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_google_path(self, mock_gs: MagicMock, mock_cls: MagicMock) -> None:
        mock_gs.return_value = _make_settings(llm_provider="google", google_api_key="goog-test")
        mock_cls.return_value = MagicMock()
        get_llm()
        mock_cls.assert_called_once()

    @patch("langchain_openai.ChatOpenAI", create=True)
    @patch("resume_operator.tools.llm_provider.get_settings")
    def test_openrouter_path(self, mock_gs: MagicMock, mock_cls: MagicMock) -> None:
        mock_gs.return_value = _make_settings(
            llm_provider="openrouter", openrouter_api_key="or-test"
        )
        mock_cls.return_value = MagicMock()
        get_llm()
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
