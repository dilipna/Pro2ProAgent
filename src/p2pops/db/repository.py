"""Data access for runs, events, ideas, and reviews.

Plain async functions over short-lived sessions. Kept deliberately flat —
this is the single place that owns SQL semantics, so the graph, the API,
and the notifier never touch the ORM directly.
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from ..config import get_settings
from ..models import AnalyzedIdea
from .engine import session
from .models import Idea, Opportunity, Review, Run, RunEvent, utcnow


# --- Runs -------------------------------------------------------------------


async def create_run(topic: str) -> Run:
    async with session() as s:
        run = Run(topic=topic)
        s.add(run)
        await s.commit()
        return run


async def get_run(run_id: str) -> Run | None:
    async with session() as s:
        return await s.get(Run, run_id)


async def list_runs(limit: int = 50) -> list[Run]:
    async with session() as s:
        rows = await s.execute(select(Run).order_by(Run.created_at.desc()).limit(limit))
        return list(rows.scalars())


async def run_count() -> int:
    async with session() as s:
        result = await s.execute(select(func.count()).select_from(Run))
        return int(result.scalar_one())


async def set_run_status(run_id: str, status: str, error: str | None = None) -> None:
    async with session() as s:
        run = await s.get(Run, run_id)
        if run is None:
            return
        run.status = status
        run.error = error
        if status in ("completed", "failed"):
            run.completed_at = utcnow()
        await s.commit()


# --- Events -----------------------------------------------------------------


async def add_event(
    run_id: str,
    agent: str,
    event_type: str,
    message: str = "",
    duration_ms: float | None = None,
) -> RunEvent:
    async with session() as s:
        event = RunEvent(
            run_id=run_id,
            agent=agent,
            event_type=event_type,
            message=message,
            duration_ms=duration_ms,
        )
        s.add(event)
        await s.commit()
        return event


async def events_after(run_id: str, after: datetime | None = None) -> list[RunEvent]:
    async with session() as s:
        query = select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.created_at)
        if after is not None:
            query = query.where(RunEvent.created_at > after)
        rows = await s.execute(query)
        return list(rows.scalars())


# --- Ideas ------------------------------------------------------------------


async def save_idea(analyzed: AnalyzedIdea, run_id: str | None = None) -> Idea:
    async with session() as s:
        idea = Idea(
            run_id=run_id,
            title=analyzed.title,
            description=analyzed.description,
            source_url=analyzed.source_url,
            score=analyzed.score,
            reasoning=analyzed.reasoning,
            status=analyzed.status,
        )
        s.add(idea)
        await s.commit()
        return idea


async def list_ideas(status: str | None = None, limit: int = 100) -> list[Idea]:
    async with session() as s:
        query = select(Idea).order_by(Idea.discovered_at.desc()).limit(limit)
        if status:
            query = query.where(Idea.status == status)
        rows = await s.execute(query)
        return list(rows.scalars())


async def set_idea_status(idea_id: str, status: str) -> None:
    async with session() as s:
        idea = await s.get(Idea, idea_id)
        if idea is not None:
            idea.status = status
            await s.commit()


async def idea_counts() -> dict[str, int]:
    async with session() as s:
        rows = await s.execute(select(Idea.status, func.count()).group_by(Idea.status))
        return dict(rows.all())


# --- Opportunities -------------------------------------------------------------


async def create_opportunity(run_id: str, idea_id: str) -> Opportunity:
    async with session() as s:
        opp = Opportunity(run_id=run_id, idea_id=idea_id)
        s.add(opp)
        await s.commit()
        return opp


async def finish_opportunity(opportunity_id: str, status: str, dossier_json: str) -> None:
    async with session() as s:
        opp = await s.get(Opportunity, opportunity_id)
        if opp is None:
            return
        opp.status = status
        opp.dossier = dossier_json
        opp.completed_at = utcnow()
        await s.commit()


async def get_opportunity(opportunity_id: str) -> Opportunity | None:
    async with session() as s:
        return await s.get(Opportunity, opportunity_id)


async def list_opportunities(status: str | None = None, limit: int = 50) -> list[Opportunity]:
    async with session() as s:
        query = select(Opportunity).order_by(Opportunity.created_at.desc()).limit(limit)
        if status:
            query = query.where(Opportunity.status == status)
        rows = await s.execute(query)
        return list(rows.scalars())


# --- Reviews ----------------------------------------------------------------


async def create_review(run_id: str, idea_id: str) -> Review:
    settings = get_settings()
    async with session() as s:
        review = Review(
            id=secrets.token_urlsafe(32),
            run_id=run_id,
            idea_id=idea_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.review_token_ttl_hours),
        )
        s.add(review)
        await s.commit()
        return review


async def record_decision(token: str, decision: str) -> Review | None:
    """Consumes a review token. Returns None if unknown, already used, or expired."""
    async with session() as s:
        review = await s.get(Review, token)
        if review is None or review.decision != "pending":
            return None
        expires = review.expires_at
        if expires.tzinfo is None:  # SQLite round-trips naive datetimes
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return None
        review.decision = decision
        review.decided_at = utcnow()
        idea = await s.get(Idea, review.idea_id)
        if idea is not None:
            idea.status = "approved" if decision == "approved" else "declined"
        await s.commit()
        return review


async def pending_reviews(run_id: str) -> list[Review]:
    async with session() as s:
        rows = await s.execute(
            select(Review).where(Review.run_id == run_id, Review.decision == "pending")
        )
        return list(rows.scalars())


async def decisions_for_run(run_id: str) -> dict[str, str]:
    """idea_id -> approved|rejected for every decided review in the run."""
    async with session() as s:
        rows = await s.execute(
            select(Review).where(Review.run_id == run_id, Review.decision != "pending")
        )
        return {r.idea_id: r.decision for r in rows.scalars()}
