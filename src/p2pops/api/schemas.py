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


class OpportunityDetailOut(OpportunityOut):
    dossier: str | None  # full OpportunityDossier JSON


class StatsOut(BaseModel):
    runs: int
    ideas_by_status: dict[str, int]
    ideas_total: int
