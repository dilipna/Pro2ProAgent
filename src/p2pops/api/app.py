"""ProToPro service API.

- /api/v1/*  — versioned JSON API consumed by the web console
- /r/{token}/{decision} — review action links from the human-gate email
  (HTML responses; unlisted, single-use, token-gated — see ADR-0002)
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .. import runner
from ..config import get_settings
from ..db import repository as repo
from ..db.engine import dispose_engine, init_db
from ..telemetry import configure_telemetry
from .schemas import (
    IdeaOut,
    OpportunityDetailOut,
    OpportunityOut,
    RunCreate,
    RunDetailOut,
    RunOut,
    StatsOut,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_telemetry()
    await init_db()
    yield
    await runner.shutdown_pipeline()
    await dispose_engine()


app = FastAPI(title="ProToPro API", version="1.0", lifespan=lifespan)

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
    return opp


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
        "Approved — the build squad takes it from here"
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
