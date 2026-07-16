"""ProToPro service API.

- /api/v1/*  — versioned JSON API consumed by the web console
- /r/{token}/{decision} — review action links from the human-gate email
  (HTML responses; unlisted, single-use, token-gated — see ADR-0002)
"""

import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .. import runner
from ..config import get_settings
from ..db import repository as repo
from ..db.engine import dispose_engine, init_db
from ..guardrails import is_search_query_allowed
from ..resilience import with_retry
from ..telemetry import configure_telemetry
from .schemas import (
    BuildCreate,
    BuildDetailOut,
    BuildOut,
    CostsOut,
    HealthOut,
    IdeaOut,
    OpportunityDetailOut,
    OpportunityOut,
    PendingReviewOut,
    ReviewDecisionIn,
    ReviewDecisionOut,
    RunCreate,
    RunDetailOut,
    RunOut,
    SearchCreate,
    SearchOut,
    ShowcaseDetailOut,
    ShowcaseItemOut,
    StatsOut,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_telemetry()
    await init_db()
    # A run's background task cannot survive the process that owns it, so any
    # run still "running"/"building" at startup is an orphan from a previous
    # process (redeploy/crash) — mark it failed instead of leaving it stuck
    # forever. Human-gate pauses are checkpointed and left resumable.
    swept = await repo.fail_orphaned_runs()
    if swept:
        logging.getLogger(__name__).warning("swept %d orphaned run(s) to failed at startup", swept)
    yield
    await runner.shutdown_pipeline()
    await dispose_engine()


app = FastAPI(title="ProToPro API", version="1.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def require_operator(authorization: str | None = Header(default=None)) -> None:
    """Bearer check for mutating endpoints. Unset API_TOKEN = open (local dev)."""
    settings = get_settings()
    if settings.api_token is None:
        return
    if authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


# --- JSON API ----------------------------------------------------------------


@app.post("/api/v1/runs", response_model=RunOut, status_code=202, dependencies=[Depends(require_operator)])
async def create_run(payload: RunCreate):
    run = await runner.start_run(payload.topic)
    return run


@app.get("/api/v1/runs", response_model=list[RunOut])
async def get_runs():
    return await repo.list_runs()


@app.get("/api/v1/runs/{run_id}", response_model=RunDetailOut)
async def get_run(run_id: str):
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/v1/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """Server-sent events: the run's event timeline, live."""
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def generator():
        cursor: datetime | None = None
        while True:
            events = await repo.events_after(run_id, after=cursor)
            for event in events:
                cursor = event.created_at
                yield {
                    "event": event.event_type,
                    "data": {
                        "agent": event.agent,
                        "message": event.message,
                        "duration_ms": event.duration_ms,
                        "at": event.created_at.isoformat(),
                    },
                }
            current = await repo.get_run(run_id)
            if current is None or current.status in ("completed", "failed"):
                yield {"event": "run_finished", "data": {"status": current.status if current else "unknown"}}
                return
            await asyncio.sleep(1.0)

    return EventSourceResponse(generator())


@app.get("/api/v1/ideas", response_model=list[IdeaOut])
async def get_ideas(status: str | None = None):
    return await repo.list_ideas(status=status)


@app.get("/api/v1/opportunities", response_model=list[OpportunityOut])
async def get_opportunities(status: str | None = None):
    return await repo.list_opportunities(status=status)


@app.get("/api/v1/opportunities/{opportunity_id}", response_model=OpportunityDetailOut)
async def get_opportunity(opportunity_id: str):
    opp = await repo.get_opportunity(opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    # No ORM `build` attribute exists (Build is a separate append-only
    # table, not a relationship) -- compose the response by hand.
    build = await repo.get_build_for_opportunity(opportunity_id)
    return OpportunityDetailOut(
        id=opp.id,
        run_id=opp.run_id,
        idea_id=opp.idea_id,
        status=opp.status,
        created_at=opp.created_at,
        completed_at=opp.completed_at,
        dossier=opp.dossier,
        build=BuildOut.model_validate(build) if build else None,
    )


@app.get("/api/v1/builds/{build_id}", response_model=BuildDetailOut)
async def get_build(build_id: str):
    build = await repo.get_build(build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


@app.post(
    "/api/v1/builds", response_model=BuildOut, status_code=202, dependencies=[Depends(require_operator)]
)
async def create_build(payload: BuildCreate):
    """Protected the same as `POST /api/v1/runs` -- strictly cheaper/lower
    blast-radius than that endpoint, so this doesn't raise the risk
    ceiling the project already accepts. No frontend button calls this;
    the console stays read-only. The operator-facing trigger is the
    `p2pops-build` CLI (`runner.execute_build`, blocking); this endpoint
    is the async equivalent (`runner.start_build`) for future automation."""
    try:
        return await runner.start_build(payload.opportunity_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "no such opportunity" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


# --- Showcase (public problem-to-product records) ------------------------------


@app.get("/api/v1/showcase", response_model=list[ShowcaseItemOut])
async def get_showcase():
    return await repo.showcase_items()


@app.get("/api/v1/showcase/{ptp_number}", response_model=ShowcaseDetailOut)
async def get_showcase_item(ptp_number: int):
    item = await repo.showcase_item_by_ptp(ptp_number)
    if item is None:
        raise HTTPException(status_code=404, detail="No such PTP item")
    return item


# --- Public keyword search ------------------------------------------------------


def _client_id(request: Request) -> str:
    """Stable, non-reversible per-caller key for rate limiting. First hop of
    X-Forwarded-For behind a proxy (Render terminates TLS in front of us),
    the socket peer otherwise. Hashed so raw addresses never hit the DB."""
    forwarded = request.headers.get("x-forwarded-for")
    raw = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return hashlib.sha256(f"p2pops-search:{raw}".encode()).hexdigest()[:32]


def _normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.lower().split())


@app.post("/api/v1/search", response_model=SearchOut)
async def public_search(payload: SearchCreate, request: Request):
    """Visitor-facing scoped discovery. Deliberately public — the spend
    controls are layered *here* (per-client and global rate limits, keyword
    dedupe, daily cost ceiling, guardrail) instead of a bearer token, and
    everything it starts still flows through the same human approval gate
    as an operator run. A visitor can surface candidates; only the operator
    can green-light a build."""
    settings = get_settings()
    keyword = payload.keyword.strip()
    normalized = _normalize_keyword(keyword)
    client_id = _client_id(request)
    now = datetime.now(UTC)
    matches = [IdeaOut.model_validate(i) for i in await repo.search_ideas(keyword)]

    # Order matters: every rejection below is recorded (so hammering never
    # earns more attempts) and none of them spends a single LLM token.
    per_client = await repo.search_requests_since(client_id, now - timedelta(hours=1))
    if per_client >= settings.search_requests_per_hour_per_client:
        await repo.create_search_request(keyword, normalized, client_id, "rate_limited")
        return SearchOut(
            outcome="rate_limited",
            message="You've reached the hourly search limit — existing matches are shown below. Try again later.",
            matches=matches,
        )

    recent = await repo.recent_search_run(normalized, now - timedelta(hours=settings.search_dedupe_hours))
    if recent is not None:
        await repo.create_search_request(keyword, normalized, client_id, "deduplicated", run_id=recent.run_id)
        return SearchOut(
            outcome="deduplicated",
            message="This keyword was searched recently — following the existing run instead of starting a new one.",
            run_id=recent.run_id,
            matches=matches,
        )

    daily = await repo.search_runs_since(now - timedelta(hours=24))
    if daily >= settings.search_runs_per_day:
        await repo.create_search_request(keyword, normalized, client_id, "rate_limited")
        return SearchOut(
            outcome="rate_limited",
            message="The daily budget for visitor-triggered discovery runs is spent. Existing matches are shown below.",
            matches=matches,
        )

    if await repo.cost_today_usd() >= settings.daily_cost_ceiling_usd:
        await repo.create_search_request(keyword, normalized, client_id, "budget_exhausted")
        return SearchOut(
            outcome="budget_exhausted",
            message="Today's LLM spend ceiling is reached, so no new discovery runs start until it resets.",
            matches=matches,
        )

    try:
        allowed = await with_retry(lambda: is_search_query_allowed(keyword), agent="search.guardrail")
    except Exception:
        await repo.create_search_request(keyword, normalized, client_id, "unavailable")
        return SearchOut(
            outcome="unavailable",
            message="Keyword validation is unavailable right now — please try again shortly.",
            matches=matches,
        )
    if not allowed:
        await repo.create_search_request(keyword, normalized, client_id, "blocked")
        return SearchOut(
            outcome="blocked",
            message="That keyword didn't pass the input guardrail — try a topic in the AI / developer-tooling space.",
            matches=matches,
        )

    # Scope the same discovery pipeline to the visitor's keyword; the suffix
    # keeps the Research Agent inside ProToPro's problem domain.
    topic = f"{keyword} — real developer / AI-engineering pain points"
    run = await runner.start_run(topic, source="search", keyword=keyword)
    await repo.create_search_request(keyword, normalized, client_id, "started", run_id=run.id)
    return SearchOut(
        outcome="started",
        message="Scoped discovery run started. New candidates go through validation and the human gate before anything is built.",
        run_id=run.id,
        matches=matches,
    )


# --- Console approval queue -------------------------------------------------------


@app.get(
    "/api/v1/reviews/pending",
    response_model=list[PendingReviewOut],
    dependencies=[Depends(require_operator)],
)
async def pending_reviews():
    """Operator-only: the tokens returned here are live approve/reject
    capabilities, so this list must never be public."""
    reviews = await repo.all_pending_reviews()
    return [
        PendingReviewOut(
            token=r.id,
            run_id=r.run_id,
            created_at=r.created_at,
            expires_at=r.expires_at,
            idea=IdeaOut.model_validate(r.idea),
        )
        for r in reviews
    ]


@app.post(
    "/api/v1/reviews/{token}",
    response_model=ReviewDecisionOut,
    dependencies=[Depends(require_operator)],
)
async def decide_review(token: str, payload: ReviewDecisionIn):
    """JSON twin of the emailed /r/{token}/{decision} links, for the
    in-console approval queue. Same single-use token semantics."""
    normalized = "approved" if payload.decision == "approve" else "rejected"
    review = await repo.record_decision(token, normalized)
    if review is None:
        raise HTTPException(status_code=410, detail="Review token invalid, already used, or expired")
    resumed = await runner.maybe_resume_after_decision(review.run_id)
    return ReviewDecisionOut(decision=normalized, run_resumed=resumed)


@app.get("/api/v1/health", response_model=HealthOut)
async def get_health(response: Response):
    """Liveness/readiness probe target (Compose healthcheck, K8s probes).
    Degraded (database unreachable) answers 503 so orchestrators act on it."""
    db_ok = await repo.ping()
    if not db_ok:
        response.status_code = 503
    return HealthOut(status="ok" if db_ok else "degraded", database=db_ok, version=app.version)


@app.get("/api/v1/costs", response_model=CostsOut)
async def get_costs():
    return await repo.cost_summary()


@app.get("/api/v1/stats", response_model=StatsOut)
async def get_stats():
    counts = await repo.idea_counts()
    return StatsOut(
        runs=await repo.run_count(),
        ideas_by_status=counts,
        ideas_total=sum(counts.values()),
    )


# --- Review action links (HTML) ----------------------------------------------


def _review_page(heading: str, body: str, accent: str = "#c23553") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>ProToPro · human gate</title></head>
<body style="margin:0;background:#0b090a;color:#f6f1f2;font-family:ui-sans-serif,system-ui,sans-serif;
display:grid;place-items:center;min-height:100vh;padding:24px">
  <div style="max-width:430px;text-align:center">
    <p style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:{accent};margin:0 0 16px">
      ProToPro · human gate</p>
    <h1 style="font-weight:600;font-size:26px;margin:0 0 12px">{heading}</h1>
    <p style="color:#948a8e;font-size:15px;line-height:1.6;margin:0">{body}</p>
  </div>
</body></html>"""


@app.get("/r/{token}/{decision}", response_class=HTMLResponse)
async def review_action(token: str, decision: str):
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=404)

    normalized = "approved" if decision == "approve" else "rejected"
    review = await repo.record_decision(token, normalized)
    if review is None:
        return HTMLResponse(
            _review_page(
                "This link is no longer valid",
                "It was already used or has expired. Nothing was changed.",
                accent="#948a8e",
            ),
            status_code=410,
        )

    resumed = await runner.maybe_resume_after_decision(review.run_id)
    heading = (
        "Approved — the venture pipeline takes it from here"
        if normalized == "approved"
        else "Rejected — noted"
    )
    body = (
        "Your decision is recorded. All reviews are in, so the pipeline resumes automatically."
        if resumed
        else "Your decision is recorded. The run resumes once the remaining ideas are decided."
    )
    return HTMLResponse(_review_page(heading, body))


def main() -> None:
    import uvicorn

    uvicorn.run("p2pops.api.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
