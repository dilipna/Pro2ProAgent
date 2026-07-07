"""Shared data models passed between agents and persisted to storage."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class DiscoveredIdea(BaseModel):
    """A single candidate problem, as surfaced by the Research Agent."""

    title: str
    description: str
    source_url: str


class ResearchReport(BaseModel):
    """Structured final output of the Research Agent -- passed as
    `response_format` to `create_react_agent` so the agent's last message is
    parsed straight into this schema instead of free-form text.
    """

    ideas: list[DiscoveredIdea] = Field(default_factory=list)


class IdeaVerdict(BaseModel):
    """Structured output of the Analyst Agent's scoring call.

    `score` deliberately has no ge/le constraint: some providers (Anthropic
    via OpenRouter/Bedrock, at least) reject a structured-output JSON schema
    that has "minimum"/"maximum" on an integer field. Clamped at runtime
    instead via the validator below.
    """

    score: int = Field(description="How worth building this is, 0-100")
    reasoning: str = Field(description="One or two sentences justifying the score")

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, value: int) -> int:
        return max(0, min(100, value))


class AnalyzedIdea(BaseModel):
    """A discovered idea after guardrails, dedupe, and scoring -- ready to persist."""

    title: str
    description: str
    source_url: str
    score: int | None = None
    reasoning: str | None = None
    status: str = "new"  # new | shortlisted | rejected | duplicate
    discovered_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
