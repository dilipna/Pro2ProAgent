"""Response/request models for the public API (v1)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RunCreate(BaseModel):
    topic: str = Field(min_length=3, max_length=300)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent: str
    event_type: str
    message: str
    duration_ms: float | None
    created_at: datetime


class IdeaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str | None
    ptp_number: int | None
    title: str
    description: str
    source_url: str
    score: int | None
    reasoning: str | None
    status: str
    discovered_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic: str
    source: str
    keyword: str | None
    status: str
    error: str | None
    created_at: datetime
    completed_at: datetime | None


class RunDetailOut(RunOut):
    events: list[EventOut]
    ideas: list[IdeaOut]


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    idea_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None


class BuildCreate(BaseModel):
    opportunity_id: str


class BuildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    run_id: str
    status: str
    deploy_url: str | None
    created_at: datetime
    completed_at: datetime | None


class BuildDetailOut(BuildOut):
    dossier: str | None  # full BuildDossier JSON


class OpportunityDetailOut(OpportunityOut):
    dossier: str | None  # full OpportunityDossier JSON
    build: BuildOut | None = None


class StatsOut(BaseModel):
    runs: int
    ideas_by_status: dict[str, int]
    ideas_total: int


class HealthOut(BaseModel):
    status: str  # "ok" | "degraded"
    database: bool
    version: str


class CostByAgentOut(BaseModel):
    agent: str
    calls: int
    tokens: int
    estimated_cost_usd: float


class CostByModelOut(BaseModel):
    provider: str
    model: str
    calls: int
    tokens: int
    estimated_cost_usd: float


class CostsOut(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    today_usd: float
    daily_ceiling_usd: float
    ceiling_exceeded: bool
    by_agent: list[CostByAgentOut]
    by_model: list[CostByModelOut]


# --- Showcase (public problem-to-product records) -----------------------------


class ShowcaseItemOut(BaseModel):
    ptp_number: int
    idea_id: str
    run_id: str | None
    title: str
    description: str
    source_url: str
    score: int | None
    status: str
    stage: str  # validated | building | live
    opportunity_id: str | None
    opportunity_status: str | None
    build_id: str | None
    build_status: str | None
    deploy_url: str | None
    discovered_at: datetime


class ShowcaseDetailOut(ShowcaseItemOut):
    reasoning: str | None = None
    opportunity_dossier: str | None = None  # OpportunityDossier JSON
    build_dossier: str | None = None  # BuildDossier JSON
    events: list[dict] = Field(default_factory=list)


# --- Public keyword search ------------------------------------------------------


class SearchCreate(BaseModel):
    keyword: str = Field(min_length=3, max_length=80)


class SearchOut(BaseModel):
    # started | deduplicated | rate_limited | blocked | budget_exhausted
    outcome: str
    message: str
    run_id: str | None = None
    matches: list[IdeaOut] = Field(default_factory=list)


# --- Console approval queue -----------------------------------------------------


class PendingReviewOut(BaseModel):
    token: str
    run_id: str
    created_at: datetime
    expires_at: datetime
    idea: IdeaOut


class ReviewDecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")


class ReviewDecisionOut(BaseModel):
    decision: str
    run_resumed: bool
