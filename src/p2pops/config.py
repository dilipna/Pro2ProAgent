"""Central settings for P2POps, loaded from environment / .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # LLM access -- swappable provider, routed through LiteLLM. This is the
    # setting that demonstrates LiteLLM's actual value: switching provider
    # is a one-line config change, no code changes.
    llm_provider: Literal["anthropic", "openrouter"] = "anthropic"

    anthropic_api_key: str | None = None
    anthropic_default_model: str = "claude-haiku-4-5-20251001"
    anthropic_builder_model: str = "claude-sonnet-5"

    openrouter_api_key: str | None = None
    openrouter_default_model: str = "anthropic/claude-haiku-4.5"
    openrouter_builder_model: str = "anthropic/claude-sonnet-4.5"

    @property
    def active_api_key(self) -> str | None:
        if self.llm_provider == "openrouter":
            return self.openrouter_api_key
        return self.anthropic_api_key

    @property
    def default_model(self) -> str:
        """LiteLLM-routable model string for high-volume agent work."""
        if self.llm_provider == "openrouter":
            return f"openrouter/{self.openrouter_default_model}"
        return f"anthropic/{self.anthropic_default_model}"

    @property
    def builder_model(self) -> str:
        """LiteLLM-routable model string for PM/Architect/build agents."""
        if self.llm_provider == "openrouter":
            return f"openrouter/{self.openrouter_builder_model}"
        return f"anthropic/{self.anthropic_builder_model}"

    # Observability
    langsmith_api_key: str | None = None
    langsmith_project: str = "p2pops"
    logfire_token: str | None = None

    # Discovery sources (later milestones)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "p2pops/0.1 (portfolio project)"

    # HITL / orchestration
    review_interval_days: int = 10

    # Storage
    database_path: str = "data/p2pops.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
