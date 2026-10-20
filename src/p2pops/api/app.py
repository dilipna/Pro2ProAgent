"""ProToPro service API.

- /api/v1/*  — versioned JSON API consumed by the web console
- /r/{token}/{decision} — review action links from the human-gate email
  (HTML responses; unlisted, single-use, token-gated — see ADR-0002)
"""

import asyncio
import hashlib
import json
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from html import escape

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse

from .. import runner
from ..briefs import ArtifactDecision, ProblemBrief, artifact_digest
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
    """Deny missing credentials unless local bypass is explicitly enabled."""
    settings = get_settings()
    if settings.api_token is None:
        if settings.environment == "development" and settings.allow_local_operator_bypass:
            return
        raise HTTPException(status_code=503, detail="Operator access is not configured")
    if not secrets.compare_digest(authorization or "", f"Bearer {settings.api_token}"):
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
    raw = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
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


# --- Explicit problem-brief handoff (no model or email on import/review) ---


@app.get("/api/v1/workspace/config")
async def workspace_config():
    settings = get_settings()
    return {
        "operator_configured": bool(settings.api_token),
        "model_configured": bool(settings.active_api_key),
        "note": "Configuration is not availability. Import and approval require no model.",
    }


@app.post("/api/v1/briefs/import", dependencies=[Depends(require_operator)])
async def import_problem_brief(request: Request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 64000:
            raise HTTPException(status_code=413, detail="Keep the brief below 64 KB")
    try:
        brief = ProblemBrief.model_validate_json(bytes(raw))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_input=False, include_context=False)) from exc
    run, idea, review, created = await repo.import_brief(brief)
    if created:
        await repo.add_event(
            run.id,
            "handoff",
            "review_requested",
            "Imported evidence snapshot; awaiting human scope review. No model called.",
        )
    return {
        "run_id": run.id,
        "idea_id": idea.id,
        "created": created,
        "snapshot_sha256": review.snapshot_sha256,
        "status": run.status,
    }


@app.get("/api/v1/briefs/{run_id}", dependencies=[Depends(require_operator)])
async def inspect_brief_run(run_id: str):
    run = await repo.get_run(run_id)
    if run is None or run.source != "brief":
        raise HTTPException(status_code=404)
    reviews = [r for r in await repo.all_pending_reviews() if r.run_id == run_id]
    ideas = [
        {
            "id": i.id,
            "status": i.status,
            "brief": json.loads(i.problem_brief),
            "approved_snapshot": await repo.approved_snapshot(i.id) if i.status == "approved" else None,
        }
        for i in run.ideas
    ]
    opportunities = await repo.opportunities_for_run(run_id)
    builds = [await repo.get_build_for_opportunity(o.id) for o in opportunities]
    return {
        "builds": [
            {"id": b.id, "status": b.status, "acceptance": json.loads(b.acceptance) if b.acceptance else None}
            for b in builds
            if b
        ],
        "run_id": run.id,
        "status": run.status,
        "ideas": ideas,
        "pending": [
            {"token": r.id, "snapshot_sha256": r.snapshot_sha256, "snapshot": json.loads(r.snapshot)}
            for r in reviews
        ],
        "events": [{"agent": e.agent, "type": e.event_type, "message": e.message} for e in run.events],
    }


@app.post("/api/v1/briefs/{run_id}/execute", dependencies=[Depends(require_operator)], status_code=202)
async def execute_approved_brief(run_id: str):
    if not get_settings().active_api_key:
        raise HTTPException(
            status_code=503, detail="No model configured; approved brief remains ready to build"
        )
    if not await repo.claim_brief_execution(run_id):
        raise HTTPException(status_code=409, detail="Run is not ready to build or execution already claimed")
    asyncio.create_task(runner.execute_brief_run(run_id))
    return {"run_id": run_id, "status": "building"}


@app.get("/api/v1/builds/{build_id}/artifact", dependencies=[Depends(require_operator)])
async def inspect_generated_artifact(build_id: str):
    build = await repo.get_build(build_id)
    if build is None or not build.dossier:
        raise HTTPException(status_code=404)
    dossier = json.loads(build.dossier)
    return {
        "build_id": build.id,
        "status": build.status,
        "artifact_sha256": artifact_digest(dossier),
        "files": dossier.get("scaffold_files", []),
        "approved_snapshot": dossier.get("approved_snapshot"),
        "acceptance": json.loads(build.acceptance) if build.acceptance else None,
        "note": "Model review is not a functional test. Test the artifact against every approved criterion.",
    }


@app.post("/api/v1/builds/{build_id}/accept", dependencies=[Depends(require_operator)])
async def record_generated_artifact_decision(build_id: str, decision: ArtifactDecision):
    if not await repo.record_artifact_decision(build_id, decision):
        raise HTTPException(
            status_code=409,
            detail="Artifact changed, required checks are missing, or a decision already exists",
        )
    return {"build_id": build_id, "decision": decision.decision, "published": False}


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
            snapshot=json.loads(r.snapshot) if r.snapshot else None,
            snapshot_sha256=r.snapshot_sha256,
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
    if normalized == "approved" and payload.snapshot_sha256 is None:
        raise HTTPException(status_code=409, detail="Inspect the current snapshot before approving")
    review = await repo.record_decision(token, normalized, payload.snapshot_sha256)
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
async def review_action(token: str, decision: str, request: Request):
    """Read-only preview. Email scanners and prefetchers cannot approve work."""
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=404)
    review = await repo.get_review(token)
    if (
        review is None
        or review.decision != "pending"
        or review.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC)
    ):
        raise HTTPException(status_code=410, detail="Review is unavailable or expired")
    idea = await repo.get_idea(review.idea_id)
    nonce = secrets.token_urlsafe(32)
    body = f"""{escape(idea.title if idea else "Idea")}<br>
    <pre style="text-align:left;white-space:pre-wrap;overflow-wrap:anywhere">{escape(review.snapshot or "No bound snapshot; reject or request a new review.")}</pre>
    Opening this page has not recorded a decision.
    <form method="post" action="/r/{escape(token)}/{decision}">
    <input type="hidden" name="confirmation" value="{nonce}">
    <input type="hidden" name="snapshot_sha256" value="{escape(review.snapshot_sha256 or "")}">
    <button type="submit" style="margin-top:24px;padding:12px 20px">Confirm {decision}</button></form>"""
    response = HTMLResponse(_review_page("Review your decision", body))
    response.set_cookie(
        "review_confirmation",
        nonce,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=600,
        path=f"/r/{token}/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.post("/r/{token}/{decision}", response_class=HTMLResponse)
async def confirm_review_action(token: str, decision: str, request: Request):
    from urllib.parse import parse_qs

    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=404)
    raw = await request.body()
    if len(raw) > 1024:
        raise HTTPException(status_code=413)
    confirmation = parse_qs(raw.decode()).get("confirmation", [""])[0]
    cookie = request.cookies.get("review_confirmation", "")
    if not cookie or not secrets.compare_digest(confirmation, cookie):
        raise HTTPException(status_code=403, detail="Open the review page and confirm deliberately")
    sha = parse_qs(raw.decode()).get("snapshot_sha256", [""])[0]
    if decision == "approve" and not sha:
        raise HTTPException(status_code=409, detail="A bound snapshot is required")
    review = await repo.record_decision(token, "approved" if decision == "approve" else "rejected", sha)
    if review is None:
        raise HTTPException(status_code=410, detail="Review is unavailable or expired")
    await runner.maybe_resume_after_decision(review.run_id)
    response = HTMLResponse(
        _review_page(
            "Decision recorded", "Your decision is recorded. Return to the console to inspect the next stage."
        )
    )
    response.delete_cookie("review_confirmation", path=f"/r/{token}/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def main() -> None:
    import uvicorn

    uvicorn.run("p2pops.api.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
