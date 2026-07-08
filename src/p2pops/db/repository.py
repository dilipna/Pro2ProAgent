"""Data access for runs, events, ideas, and reviews.

Plain async functions over short-lived sessions. Kept deliberately flat —
this is the single place that owns SQL semantics, so the graph, the API,
and the notifier never touch the ORM directly.
"""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..models import AnalyzedIdea
from .engine import session
from .models import (
    Build,
    Idea,
    LlmCall,
    Opportunity,
    Review,
    Run,
    RunEvent,
    SearchRequest,
    utcnow,
)

# PTP-001..003 are the pre-database seeded showcase cards (real early
# pipeline output, statically mirrored in the web tier) — database-assigned
# numbering starts after them so the public sequence never collides.
PTP_SEED_MAX = 3

# --- Health -----------------------------------------------------------------


async def ping() -> bool:
    """Cheap end-to-end database check for health probes. Returns False
    rather than raising so the health endpoint decides the response shape."""
    try:
        async with session() as s:
            await s.execute(select(1))
        return True
    except Exception:
        return False


# --- Runs -------------------------------------------------------------------


async def create_run(topic: str, source: str = "operator", keyword: str | None = None) -> Run:
    async with session() as s:
        run = Run(topic=topic, source=source, keyword=keyword)
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
        ptp_number: int | None = None
        if analyzed.status == "shortlisted":
            # Assign the next public PTP number at shortlist time — validated
            # problems get a number, rejected/duplicate noise never burns one.
            # Computed and inserted in one transaction; SQLite's single-writer
            # model makes this collision-safe at current scale.
            current = await s.execute(select(func.max(Idea.ptp_number)))
            ptp_number = max(current.scalar_one() or 0, PTP_SEED_MAX) + 1
        idea = Idea(
            run_id=run_id,
            ptp_number=ptp_number,
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


async def get_idea(idea_id: str) -> Idea | None:
    async with session() as s:
        return await s.get(Idea, idea_id)


async def get_idea_by_ptp(ptp_number: int) -> Idea | None:
    async with session() as s:
        rows = await s.execute(select(Idea).where(Idea.ptp_number == ptp_number))
        return rows.scalars().first()


async def search_ideas(keyword: str, limit: int = 6) -> list[Idea]:
    """Case-insensitive substring match over numbered (validated) ideas —
    the instant-response half of the public keyword search."""
    pattern = f"%{keyword.strip()}%"
    async with session() as s:
        rows = await s.execute(
            select(Idea)
            .where(
                Idea.ptp_number.is_not(None),
                Idea.title.ilike(pattern) | Idea.description.ilike(pattern),
            )
            .order_by(Idea.ptp_number.desc())
            .limit(limit)
        )
        return list(rows.scalars())


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


async def reviewed_ideas() -> list[Idea]:
    """Ideas with a human decision recorded. `record_decision` overwrites
    `Idea.status` to approved|declined directly, so no join with `reviews`
    is needed -- these two status values *are* the human label."""
    async with session() as s:
        rows = await s.execute(
            select(Idea)
            .where(Idea.status.in_(("approved", "declined")))
            .order_by(Idea.discovered_at)
        )
        return list(rows.scalars())


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


# --- Builds -------------------------------------------------------------------


async def create_build(run_id: str, opportunity_id: str) -> Build:
    async with session() as s:
        build = Build(run_id=run_id, opportunity_id=opportunity_id)
        s.add(build)
        await s.commit()
        return build


async def finish_build(build_id: str, status: str, dossier_json: str) -> None:
    async with session() as s:
        build = await s.get(Build, build_id)
        if build is None:
            return
        build.status = status
        build.dossier = dossier_json
        build.completed_at = utcnow()
        await s.commit()


async def get_build(build_id: str) -> Build | None:
    async with session() as s:
        return await s.get(Build, build_id)


async def get_build_for_opportunity(opportunity_id: str) -> Build | None:
    """Most recent build for this opportunity (Build is append-only)."""
    async with session() as s:
        rows = await s.execute(
            select(Build)
            .where(Build.opportunity_id == opportunity_id)
            .order_by(Build.created_at.desc())
            .limit(1)
        )
        return rows.scalars().first()


async def list_builds(status: str | None = None, limit: int = 50) -> list[Build]:
    async with session() as s:
        query = select(Build).order_by(Build.created_at.desc()).limit(limit)
        if status:
            query = query.where(Build.status == status)
        rows = await s.execute(query)
        return list(rows.scalars())


async def set_build_deploy_url(build_id: str, url: str) -> None:
    async with session() as s:
        build = await s.get(Build, build_id)
        if build is not None:
            build.deploy_url = url
            await s.commit()


# --- Showcase ------------------------------------------------------------------


async def showcase_items(limit: int = 24) -> list[dict]:
    """Numbered ideas with their lifecycle stage, newest first. Lifecycle is
    computed in code from the idea/opportunity/build chain — one honest
    place decides what 'Building' vs 'Live' means."""
    async with session() as s:
        idea_rows = await s.execute(
            select(Idea)
            # Human-declined problems leave the public showcase (their number
            # is never reused); they stay fully visible in the console.
            .where(Idea.ptp_number.is_not(None), Idea.status != "declined")
            .order_by(Idea.ptp_number.desc())
            .limit(limit)
        )
        ideas = list(idea_rows.scalars())
        items = []
        for idea in ideas:
            opp_rows = await s.execute(
                select(Opportunity)
                .where(Opportunity.idea_id == idea.id)
                .order_by(Opportunity.created_at.desc())
                .limit(1)
            )
            opp = opp_rows.scalars().first()
            build = None
            if opp is not None:
                build_rows = await s.execute(
                    select(Build)
                    .where(Build.opportunity_id == opp.id)
                    .order_by(Build.created_at.desc())
                    .limit(1)
                )
                build = build_rows.scalars().first()
            items.append(_showcase_item(idea, opp, build))
        return items


def _showcase_item(idea: Idea, opp: Opportunity | None, build: Build | None) -> dict:
    if build is not None and build.status == "complete" and build.deploy_url:
        stage = "live"
    elif build is not None and build.status in ("scaffolding", "complete", "needs_revision"):
        # complete-without-URL / needs_revision are still "in build" publicly:
        # the product exists but hasn't cleared publish, so no Live claim.
        stage = "building"
    elif opp is not None and opp.status in ("validating", "complete"):
        stage = "building"
    else:
        stage = "validated"
    return {
        "ptp_number": idea.ptp_number,
        "idea_id": idea.id,
        "run_id": idea.run_id,
        "title": idea.title,
        "description": idea.description,
        "source_url": idea.source_url,
        "score": idea.score,
        "status": idea.status,
        "stage": stage,
        "opportunity_id": opp.id if opp else None,
        "opportunity_status": opp.status if opp else None,
        "build_id": build.id if build else None,
        "build_status": build.status if build else None,
        "deploy_url": build.deploy_url if build else None,
        "discovered_at": idea.discovered_at,
    }


async def showcase_item_by_ptp(ptp_number: int) -> dict | None:
    idea = await get_idea_by_ptp(ptp_number)
    if idea is None:
        return None
    async with session() as s:
        opp_rows = await s.execute(
            select(Opportunity)
            .where(Opportunity.idea_id == idea.id)
            .order_by(Opportunity.created_at.desc())
            .limit(1)
        )
        opp = opp_rows.scalars().first()
        build = None
        if opp is not None:
            build_rows = await s.execute(
                select(Build).where(Build.opportunity_id == opp.id).order_by(Build.created_at.desc()).limit(1)
            )
            build = build_rows.scalars().first()
    item = _showcase_item(idea, opp, build)
    item["reasoning"] = idea.reasoning
    item["opportunity_dossier"] = opp.dossier if opp else None
    item["build_dossier"] = build.dossier if build else None
    if idea.run_id:
        item["events"] = [
            {
                "agent": e.agent,
                "event_type": e.event_type,
                "message": e.message,
                "duration_ms": e.duration_ms,
                "created_at": e.created_at,
            }
            for e in await events_after(idea.run_id)
        ]
    else:
        item["events"] = []
    return item


# --- Search requests (public keyword search) -----------------------------------


async def create_search_request(
    keyword: str, normalized: str, client_id: str, outcome: str, run_id: str | None = None
) -> SearchRequest:
    async with session() as s:
        req = SearchRequest(
            keyword=keyword, normalized=normalized, client_id=client_id, outcome=outcome, run_id=run_id
        )
        s.add(req)
        await s.commit()
        return req


async def search_requests_since(client_id: str | None, since: datetime) -> int:
    """Submission count in the window — all outcomes, so hammering a
    rate-limited endpoint never earns more attempts."""
    async with session() as s:
        query = select(func.count()).select_from(SearchRequest).where(SearchRequest.created_at > since)
        if client_id is not None:
            query = query.where(SearchRequest.client_id == client_id)
        return int((await s.execute(query)).scalar_one())


async def search_runs_since(since: datetime) -> int:
    """Runs actually *started* by search in the window (the global daily cap)."""
    async with session() as s:
        query = (
            select(func.count())
            .select_from(SearchRequest)
            .where(SearchRequest.created_at > since, SearchRequest.outcome == "started")
        )
        return int((await s.execute(query)).scalar_one())


async def recent_search_run(normalized: str, since: datetime) -> SearchRequest | None:
    """A prior started run for the same normalized keyword — the dedupe hit."""
    async with session() as s:
        rows = await s.execute(
            select(SearchRequest)
            .where(
                SearchRequest.normalized == normalized,
                SearchRequest.outcome == "started",
                SearchRequest.created_at > since,
            )
            .order_by(SearchRequest.created_at.desc())
            .limit(1)
        )
        return rows.scalars().first()


# --- Reviews ----------------------------------------------------------------


async def create_review(run_id: str, idea_id: str) -> Review:
    settings = get_settings()
    async with session() as s:
        review = Review(
            id=secrets.token_urlsafe(32),
            run_id=run_id,
            idea_id=idea_id,
            expires_at=datetime.now(UTC) + timedelta(hours=settings.review_token_ttl_hours),
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
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
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


async def all_pending_reviews() -> list[Review]:
    """Every undecided, unexpired review across all runs — the console's
    approval queue. Ideas come via the selectin relationship. Expiry is
    filtered in Python: SQLite round-trips these datetimes naive (see
    record_decision), so a SQL comparison against an aware bound value
    would be comparing differently-shaped ISO strings."""
    now = datetime.now(UTC)
    async with session() as s:
        rows = await s.execute(
            select(Review)
            .options(selectinload(Review.idea))  # consumed after the session closes
            .where(Review.decision == "pending")
            .order_by(Review.created_at.desc())
        )
        pending = []
        for review in rows.scalars():
            expires = review.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if expires > now:
                pending.append(review)
        return pending


async def decisions_for_run(run_id: str) -> dict[str, str]:
    """idea_id -> approved|rejected for every decided review in the run."""
    async with session() as s:
        rows = await s.execute(
            select(Review).where(Review.run_id == run_id, Review.decision != "pending")
        )
        return {r.idea_id: r.decision for r in rows.scalars()}


# --- LLM cost tracking --------------------------------------------------------


async def record_llm_call(
    agent: str, provider: str, model: str, input_tokens: int, output_tokens: int, estimated_cost_usd: float
) -> None:
    async with session() as s:
        s.add(
            LlmCall(
                agent=agent,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimated_cost_usd,
            )
        )
        await s.commit()


async def cost_today_usd() -> float:
    """Estimated spend since UTC midnight — the number the daily cost
    ceiling (public-search circuit breaker + console alert) compares against."""
    midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    async with session() as s:
        total = await s.execute(
            select(func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0)).where(
                LlmCall.created_at > midnight
            )
        )
        return float(total.scalar_one())


async def cost_summary() -> dict:
    """Aggregate spend: totals plus a breakdown by agent and by model.
    Powers the console's LLM cost panel."""
    settings = get_settings()
    today_usd = await cost_today_usd()
    async with session() as s:
        totals = (
            await s.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(LlmCall.input_tokens), 0),
                    func.coalesce(func.sum(LlmCall.output_tokens), 0),
                    func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0),
                )
            )
        ).one()
        calls, input_tokens, output_tokens, cost = totals

        by_agent_rows = await s.execute(
            select(
                LlmCall.agent,
                func.count(),
                func.coalesce(func.sum(LlmCall.input_tokens + LlmCall.output_tokens), 0),
                func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0),
            ).group_by(LlmCall.agent)
        )
        by_model_rows = await s.execute(
            select(
                LlmCall.provider,
                LlmCall.model,
                func.count(),
                func.coalesce(func.sum(LlmCall.input_tokens + LlmCall.output_tokens), 0),
                func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0),
            ).group_by(LlmCall.provider, LlmCall.model)
        )

        return {
            "calls": int(calls),
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "estimated_cost_usd": float(cost),
            "today_usd": today_usd,
            "daily_ceiling_usd": settings.daily_cost_ceiling_usd,
            "ceiling_exceeded": today_usd >= settings.daily_cost_ceiling_usd,
            "by_agent": [
                {"agent": agent, "calls": int(c), "tokens": int(t), "estimated_cost_usd": float(cost)}
                for agent, c, t, cost in by_agent_rows
            ],
            "by_model": [
                {
                    "provider": provider,
                    "model": model,
                    "calls": int(c),
                    "tokens": int(t),
                    "estimated_cost_usd": float(cost),
                }
                for provider, model, c, t, cost in by_model_rows
            ],
        }
