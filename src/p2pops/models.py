"""Shared data models passed between agents and persisted to storage."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator
from pydantic.json_schema import SkipJsonSchema


class XploreMoreProvenance(BaseModel):
    """Where an idea's demand evidence came from, when it was discovered via
    XploreMore's problem API (ADR-0012).

    Always attached by code from the tool results the agent actually
    received (`tools/xploremore.attach_provenance`), never taken from the
    model's output -- an LLM can quote a problem id it never saw, and a
    showcase card claiming "23 people" must trace back to a real response.
    """

    problem_id: int
    voices: int
    sources: int
    platforms: list[str] = Field(default_factory=list)
    demand: float | None = None
    evidence_urls: list[str] = Field(default_factory=list)

    @property
    def card_line(self) -> str:
        people = "person" if self.voices == 1 else "people"
        sources = "source" if self.sources == 1 else "sources"
        return f"Discovered via XploreMore: {self.voices} {people} across {self.sources} {sources}"


class DiscoveredIdea(BaseModel):
    """A single candidate problem, as surfaced by the Research Agent."""

    title: str
    description: str
    source_url: str
    problem_id: int | None = Field(
        default=None,
        description=(
            "The XploreMore problem id, copied exactly from a find_problems or get_problem "
            "result, when this idea comes from one. Leave null otherwise."
        ),
    )
    # Hidden from the model's response schema: code fills it (see
    # XploreMoreProvenance), and overwrites anything the model sends.
    provenance: SkipJsonSchema[XploreMoreProvenance | None] = None


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
    problem_id: int | None = None
    provenance: XploreMoreProvenance | None = None
    score: int | None = None
    reasoning: str | None = None
    status: str = "new"  # new | shortlisted | rejected | duplicate
    discovered_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
