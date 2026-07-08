"""Central settings for P2POps, loaded from environment / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Optional secret/config fields where "KEY=" (blank) in .env must mean
# "unset", not the literal empty string -- see _blank_to_none below. This is
# every `str | None` field backed by an env var that a user might leave
# blank in .env.example.
_BLANKABLE_FIELDS = (
    "anthropic_api_key",
    "openrouter_api_key",
    "groq_api_key",
    "langsmith_api_key",
    "logfire_token",
    "reddit_client_id",
    "reddit_client_secret",
    "review_email_to",
    "resend_api_key",
    "api_token",
    "vercel_token",
    "vercel_team_id",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # LLM access -- swappable provider, routed through LiteLLM. This is the
    # setting that demonstrates LiteLLM's actual value: switching provider
    # is a one-line config change, no code changes.
    llm_provider: Literal["anthropic", "openrouter", "groq"] = "anthropic"

    anthropic_api_key: str | None = None
    anthropic_default_model: str = "claude-haiku-4-5-20251001"
    anthropic_builder_model: str = "claude-sonnet-5"

    openrouter_api_key: str | None = None
    openrouter_default_model: str = "anthropic/claude-haiku-4.5"
    openrouter_builder_model: str = "anthropic/claude-sonnet-4.5"

    # Groq: fast inference via an OpenAI-compatible endpoint. Model choice
    # here is deliberately about rate-limit headroom, not just capability --
    # a live run hit gpt-oss-20b's on-demand tier ceiling of 8000 tokens/min
    # (shared org-wide, a *sliding* window, so it isn't fixed by spacing
    # requests out) after just one search and one article read. Measured
    # actual per-model limits on this account before choosing:
    #   llama-3.1-8b-instant            6,000 TPM
    #   qwen/qwen3-32b                  6,000 TPM
    #   openai/gpt-oss-20b              8,000 TPM
    #   openai/gpt-oss-120b             8,000 TPM
    #   llama-3.3-70b-versatile        12,000 TPM
    #   llama-4-scout-17b-16e-instruct 30,000 TPM  <- picked: verified tool
    #                                                calling + structured
    #                                                output work, 3.75x the
    #                                                headroom of gpt-oss-20b
    groq_api_key: str | None = None
    groq_default_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    groq_builder_model: str = "openai/gpt-oss-120b"

    @property
    def active_api_key(self) -> str | None:
        if self.llm_provider == "openrouter":
            return self.openrouter_api_key
        if self.llm_provider == "groq":
            return self.groq_api_key
        return self.anthropic_api_key

    @property
    def default_model(self) -> str:
        """LiteLLM-routable model string for high-volume agent work."""
        if self.llm_provider == "openrouter":
            return f"openrouter/{self.openrouter_default_model}"
        if self.llm_provider == "groq":
            return f"groq/{self.groq_default_model}"
        return f"anthropic/{self.anthropic_default_model}"

    @property
    def builder_model(self) -> str:
        """LiteLLM-routable model string for PM/Architect/build agents."""
        if self.llm_provider == "openrouter":
            return f"openrouter/{self.openrouter_builder_model}"
        if self.llm_provider == "groq":
            return f"groq/{self.groq_builder_model}"
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
    review_token_ttl_hours: int = 72

    # Email delivery for the human gate. With no RESEND_API_KEY set, the
    # console adapter logs the review email instead of sending it.
    review_email_to: str | None = None
    resend_api_key: str | None = None
    resend_from: str = "ProToPro <onboarding@resend.dev>"

    # Public base URL used to build review action links.
    app_base_url: str = "http://localhost:8000"

    # Optional bearer token protecting mutating API endpoints. Unset = open
    # (single-operator local development).
    api_token: str | None = None

    # Product publishing (build-squad publish stage). Unset = the publish
    # stage skips honestly (build completes, no live URL) rather than failing.
    vercel_token: str | None = None
    vercel_team_id: str | None = None

    # Public keyword-search guardrails (Feature 2). All three are spend
    # controls on an endpoint any visitor can hit — see the search route.
    search_requests_per_hour_per_client: int = 3
    search_runs_per_day: int = 8
    search_dedupe_hours: int = 24
    # Daily estimated-spend ceiling (USD) across ALL LLM calls; when today's
    # ledger total crosses it, public search stops starting new runs and the
    # console shows a cost alert. Operator-triggered runs are not blocked.
    daily_cost_ceiling_usd: float = 1.0

    # Storage
    data_dir: str = "data"
    database_path: str = "data/p2pops.db"  # legacy sqlite3 store (pre-Phase 1)

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.data_dir}/protopro.db"

    @property
    def checkpoint_db_path(self) -> str:
        return f"{self.data_dir}/checkpoints.db"

    @field_validator(*_BLANKABLE_FIELDS, mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        """`KEY=` in .env parses as "" (a truthy-looking but empty secret),
        not None -- which silently defeats every `if settings.x:` check and,
        worse, made an unset API_TOKEN compare against "Bearer " instead of
        being treated as open access. Blank strings mean unset, always."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
