"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration loaded from environment variables / .env file."""

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""
    log_level: str = "INFO"
    ats_skip_threshold: float = 0.9
    resume_template: str = "default"  # default | compact | modern — stub for future templates
    resume_style_path: str = ""  # path to a StyleTemplate YAML; overridden by `run --style` (#72)
    enrich_threshold: int = 6  # kept+reworded items below which `run` offers an enrich session
    resume_max_iterations: int = 3  # #78 iterative tailor loop cap; overridden by `run --max-iter`

    # #81 ATSReport composite weights — sum to 1.0. Tune per JD category if
    # the default emphasis doesn't fit (e.g. hiring for a soft-skill-heavy
    # role → bump ats_weight_soft at the expense of ats_weight_hard).
    ats_weight_hard: float = 0.40
    ats_weight_soft: float = 0.20
    ats_weight_structural: float = 0.15
    ats_weight_title: float = 0.10
    ats_weight_measurable: float = 0.10
    ats_weight_tone: float = 0.05

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
