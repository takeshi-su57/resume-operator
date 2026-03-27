"""Tests for application configuration."""

from unittest.mock import patch

from resume_operator.config import Settings


class TestDefaultSettings:
    """Verify Settings defaults match .env.example."""

    def test_default_llm_provider(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.llm_provider == "openai"

    def test_default_llm_model(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.llm_model == "gpt-4o"

    def test_default_api_keys_empty(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.openai_api_key == ""
        assert settings.anthropic_api_key == ""
        assert settings.google_api_key == ""
        assert settings.openrouter_api_key == ""

    def test_default_log_level(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.log_level == "INFO"


class TestSettingsFromEnv:
    """Settings should load values from environment variables."""

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "anthropic",
            "LLM_MODEL": "claude-sonnet-4-6-20250514",
            "ANTHROPIC_API_KEY": "sk-ant-test-key",
            "LOG_LEVEL": "DEBUG",
        },
    )
    def test_settings_from_env(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.llm_provider == "anthropic"
        assert settings.llm_model == "claude-sonnet-4-6-20250514"
        assert settings.anthropic_api_key == "sk-ant-test-key"
        assert settings.log_level == "DEBUG"

    @patch.dict(
        "os.environ",
        {
            "LLM_PROVIDER": "google",
            "GOOGLE_API_KEY": "goog-key-123",
        },
    )
    def test_google_provider_from_env(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.llm_provider == "google"
        assert settings.google_api_key == "goog-key-123"

    @patch.dict(
        "os.environ",
        {
            "OPENROUTER_API_KEY": "or-key-456",
        },
    )
    def test_single_key_from_env(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.openrouter_api_key == "or-key-456"
        assert settings.openai_api_key == ""
