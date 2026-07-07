"""SQLAlchemy models — the durable record of everything the agent company does.

Schema management: `Base.metadata.create_all` at startup for now. Alembic
lands once the Phase 1 schema stabilizes and there is production data worth
migrating (deviation from ADR-0001 logged in implementation-notes.md).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Run(Base):
    """One end-to-end pipeline execution."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    topic: Mapped[str] = mapped_column(Text)
    # running | awaiting_review | building | completed | failed
    status: Mapped[str] = mapped_column(String(20), default="running")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run", order_by="RunEvent.created_at", lazy="selectin"
    )
    ideas: Mapped[list["Idea"]] = relationship(back_populates="run", lazy="selectin")


class RunEvent(Base):
    """One observable step inside a run — the AgentOps timeline."""

    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    agent: Mapped[str] = mapped_column(String(40))  # research | analyst | supervisor | human-gate | system
    # stage_started | stage_completed | idea_discovered | idea_analyzed |
    # review_requested | review_decided | error
    event_type: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[float | None] = mapped_column(Float, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[Run] = relationship(back_populates="events")


class Idea(Base):
    """A discovered problem and its journey through validation."""

    __tablename__ = "ideas"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), index=True, default=None)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer, default=None)
    reasoning: Mapped[str | None] = mapped_column(Text, default=None)
    # new | shortlisted | rejected | duplicate | approved | declined
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[Run | None] = relationship(back_populates="ideas")
    reviews: Mapped[list["Review"]] = relationship(back_populates="idea", lazy="selectin")


class Opportunity(Base):
    """One approved idea's journey through the venture pipeline.

    `dossier` holds the full OpportunityDossier JSON — every artifact, gate
    decision, and refinement round, reproducible and self-contained.
    """

    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    idea_id: Mapped[str] = mapped_column(ForeignKey("ideas.id"), index=True)
    # validating | complete | rejected | parked | failed
    status: Mapped[str] = mapped_column(String(20), default="validating", index=True)
    dossier: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Build(Base):
    """One build-squad run for a `complete` Opportunity.

    `run_id` is carried (not just `opportunity_id`) so build-squad graph
    nodes can log events the same way every other stage does -- the
    AgentOps timeline is a Run-scoped concept in this codebase, same as
    `Opportunity`. Append-only like Opportunity/Idea: a fresh
    `p2pops-build` run always inserts a new row rather than upserting one.
    """

    __tablename__ = "builds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    # scaffolding | complete | needs_revision | failed
    status: Mapped[str] = mapped_column(String(20), default="scaffolding", index=True)
    dossier: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class LlmCall(Base):
    """One structured-output LLM call's token usage and estimated cost.

    A global ledger, not run-scoped: `agent` (e.g. "venture/validator",
    "analyst.scorer", "research") is the attribution key the console cost
    view aggregates by. No FK to `runs` — threading run_id through every
    agent call site (research's ReAct loop, all ten venture/build agents)
    for this alone was judged not worth the invasiveness; see
    docs/adr/0009-cost-tracking.md for the scope call.
    """

    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Review(Base):
    """A single-use human decision token for one shortlisted idea.

    The id doubles as the unguessable token in emailed approve/reject
    links; a row is consumed the first time a decision is recorded.
    """

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    idea_id: Mapped[str] = mapped_column(ForeignKey("ideas.id"), index=True)
    # pending | approved | rejected
    decision: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    idea: Mapped[Idea] = relationship(back_populates="reviews")
