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


async def test_health_endpoint(client):
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] is True


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


async def test_opportunity_detail_includes_build_when_present(client):
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea("approved"), run_id=run.id)
    opportunity = await repo.create_opportunity(run.id, idea.id)
    await repo.finish_opportunity(opportunity.id, "complete", '{"status": "complete"}')

    # No build yet.
    detail = (await client.get(f"/api/v1/opportunities/{opportunity.id}")).json()
    assert detail["status"] == "complete"
    assert detail["build"] is None

    build = await repo.create_build(run.id, opportunity.id)
    await repo.finish_build(build.id, "complete", '{"status": "complete"}')

    detail = (await client.get(f"/api/v1/opportunities/{opportunity.id}")).json()
    assert detail["build"]["id"] == build.id
    assert detail["build"]["status"] == "complete"

    assert (await client.get("/api/v1/opportunities/nope")).status_code == 404


async def test_get_build_detail_and_404(client):
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea("approved"), run_id=run.id)
    opportunity = await repo.create_opportunity(run.id, idea.id)
    build = await repo.create_build(run.id, opportunity.id)
    await repo.finish_build(build.id, "needs_revision", '{"status": "needs_revision"}')

    detail = (await client.get(f"/api/v1/builds/{build.id}")).json()
    assert detail["status"] == "needs_revision"
    assert detail["dossier"] == '{"status": "needs_revision"}'

    assert (await client.get("/api/v1/builds/nope")).status_code == 404


async def test_create_build_rejects_incomplete_opportunity(client):
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea("approved"), run_id=run.id)
    opportunity = await repo.create_opportunity(run.id, idea.id)  # still "validating"

    resp = await client.post("/api/v1/builds", json={"opportunity_id": opportunity.id})
    assert resp.status_code == 400

    assert (await client.post("/api/v1/builds", json={"opportunity_id": "nope"})).status_code == 404


async def test_create_build_starts_for_complete_opportunity(client, monkeypatch):
    # Don't launch the real build-squad graph in an API test -- just
    # confirm the endpoint validates and delegates to runner.start_build.
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea("approved"), run_id=run.id)
    opportunity = await repo.create_opportunity(run.id, idea.id)
    await repo.finish_opportunity(opportunity.id, "complete", '{"status": "complete"}')

    async def fake_start_build(opportunity_id: str):
        return await repo.create_build(run.id, opportunity_id)

    monkeypatch.setattr(runner, "start_build", fake_start_build)

    resp = await client.post("/api/v1/builds", json={"opportunity_id": opportunity.id})
    assert resp.status_code == 202
    assert resp.json()["opportunity_id"] == opportunity.id


async def test_blank_api_token_in_env_means_open_not_locked(client, monkeypatch):
    """`API_TOKEN=` (blank) in .env must mean unset, not a literal empty
    secret -- regression test for the bug where every request was silently
    denied because "" != None."""
    monkeypatch.setenv("API_TOKEN", "")
    from p2pops.config import get_settings

    get_settings.cache_clear()

    # Don't actually launch the live pipeline -- this test is only about
    # whether the auth dependency lets the request through.
    async def fake_start_run(topic: str):
        return await repo.create_run(topic)

    monkeypatch.setattr(runner, "start_run", fake_start_run)

    try:
        allowed = await client.post("/api/v1/runs", json={"topic": "agent tooling"})
        assert allowed.status_code == 202
    finally:
        monkeypatch.delenv("API_TOKEN")
        get_settings.cache_clear()
