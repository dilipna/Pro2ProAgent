"""SQLAlchemy models — the durable record of everything the agent company does.

Schema management: `Base.metadata.create_all` at startup for now. Alembic
lands once the Phase 1 schema stabilizes and there is production data worth
migrating (deviation from ADR-0001 logged in implementation-notes.md).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
