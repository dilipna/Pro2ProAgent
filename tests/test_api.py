import httpx
import pytest
from conftest import make_idea

from p2pops import runner
from p2pops.api.app import app
from p2pops.db import repository as repo


@pytest.fixture
async def client(db, monkeypatch):
    # Keep API tests hermetic: no LangGraph resume, no real pipeline.
    async def fake_resume(run_id: str) -> bool:
        return not await repo.pending_reviews(run_id)

    monkeypatch.setattr(runner, "maybe_resume_after_decision", fake_resume)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_stats_and_ideas_endpoints(client):
    run = await repo.create_run("t")
    await repo.save_idea(make_idea("shortlisted"), run_id=run.id)

    stats = (await client.get("/api/v1/stats")).json()
    assert stats["runs"] == 1
    assert stats["ideas_total"] == 1

    ideas = (await client.get("/api/v1/ideas", params={"status": "shortlisted"})).json()
    assert len(ideas) == 1
    assert ideas[0]["title"] == "Test problem"


async def test_run_detail_and_404(client):
    run = await repo.create_run("t")
    await repo.add_event(run.id, "research", "stage_started", "x")

    detail = (await client.get(f"/api/v1/runs/{run.id}")).json()
    assert detail["topic"] == "t"
    assert len(detail["events"]) == 1

    assert (await client.get("/api/v1/runs/nope")).status_code == 404


async def test_review_link_flow(client):
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea(), run_id=run.id)
    review = await repo.create_review(run.id, idea.id)

    page = await client.get(f"/r/{review.id}/approve")
    assert page.status_code == 200
    assert "Approved" in page.text

    # Single use: second click is politely refused.
    again = await client.get(f"/r/{review.id}/approve")
    assert again.status_code == 410

    ideas = (await client.get("/api/v1/ideas", params={"status": "approved"})).json()
    assert [i["id"] for i in ideas] == [idea.id]


async def test_create_run_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret123")
    from p2pops.config import get_settings

    get_settings.cache_clear()
    try:
        denied = await client.post("/api/v1/runs", json={"topic": "agent tooling"})
        assert denied.status_code == 401
    finally:
        monkeypatch.delenv("API_TOKEN")
        get_settings.cache_clear()
