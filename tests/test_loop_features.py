"""Tests for the closed Discover -> Publish loop and the public keyword
search: PTP numbering, showcase lifecycle, product packaging, deterministic
file targeting, the publish stage (offline), and the search endpoint's
spend controls.
"""

import httpx
import pytest

from conftest import make_idea
from p2pops import publish, runner
from p2pops.api import app as app_module
from p2pops.api.app import app
from p2pops.build.schemas import ComponentSpec, ScaffoldFile
from p2pops.build.scoring import scaffold_target, scaffold_targets
from p2pops.config import get_settings
from p2pops.db import repository as repo

# --- PTP numbering ---------------------------------------------------------------


async def test_ptp_numbers_assigned_sequentially_to_shortlisted_only(db):
    run = await repo.create_run("t")
    first = await repo.save_idea(make_idea("shortlisted", title="A"), run_id=run.id)
    noise = await repo.save_idea(make_idea("rejected", title="B"), run_id=run.id)
    second = await repo.save_idea(make_idea("shortlisted", title="C"), run_id=run.id)

    # Seeds occupy 1-3; database numbering starts at 4 and never burns a
    # number on rejected noise.
    assert first.ptp_number == 4
    assert noise.ptp_number is None
    assert second.ptp_number == 5

    assert (await repo.get_idea_by_ptp(5)).id == second.id
    assert await repo.get_idea_by_ptp(999) is None


# --- Showcase lifecycle ------------------------------------------------------------


async def test_showcase_stage_progression(db):
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea("shortlisted"), run_id=run.id)

    items = await repo.showcase_items()
    assert [i["stage"] for i in items] == ["validated"]

    opp = await repo.create_opportunity(run.id, idea.id)
    assert (await repo.showcase_items())[0]["stage"] == "building"

    build = await repo.create_build(run.id, opp.id)
    await repo.finish_build(build.id, "complete", "{}")
    # complete but unpublished: still not allowed to claim Live
    assert (await repo.showcase_items())[0]["stage"] == "building"

    await repo.set_build_deploy_url(build.id, "https://ptp-004-thing.vercel.app")
    item = (await repo.showcase_items())[0]
    assert item["stage"] == "live"
    assert item["deploy_url"] == "https://ptp-004-thing.vercel.app"

    detail = await repo.showcase_item_by_ptp(item["ptp_number"])
    assert detail["build_dossier"] == "{}"
    assert isinstance(detail["events"], list)


# --- Deterministic file targeting ----------------------------------------------------


def test_scaffold_target_maps_browser_techs():
    assert scaffold_target(ComponentSpec(name="p", responsibility="r", tech="HTML page")) == (
        "index.html",
        "html",
    )
    assert scaffold_target(
        ComponentSpec(name="l", responsibility="r", tech="JavaScript browser logic with localStorage")
    ) == ("app.js", "javascript")
    assert scaffold_target(ComponentSpec(name="s", responsibility="r", tech="CSS stylesheet")) == (
        "styles.css",
        "css",
    )


def test_scaffold_targets_unique_paths_and_stable_first_claim():
    components = [
        ComponentSpec(name="Main Page", responsibility="r", tech="HTML page"),
        ComponentSpec(name="Help Page", responsibility="r", tech="HTML page"),
        ComponentSpec(name="App Logic", responsibility="r", tech="JavaScript logic"),
    ]
    targets = scaffold_targets(components)
    assert targets["Main Page"] == ("index.html", "html")
    assert targets["Help Page"] == ("help-page-index.html", "html")
    assert targets["App Logic"] == ("app.js", "javascript")
    assert len({path for path, _ in targets.values()}) == 3


# --- Packaging ------------------------------------------------------------------------


def _file(component: str, path: str, content: str) -> ScaffoldFile:
    return ScaffoldFile(component=component, path=path, language="html", content=content)


def test_package_product_promotes_html_entry_and_injects_badge():
    files = [
        _file("Page", "main.html", "<html><body><h1>Hi</h1></body></html>"),
        _file("Logic", "app.js", "console.log('x')"),
        _file("Docs", "schema.sql", "CREATE TABLE t (id int);"),  # not browser-servable
    ]
    bundle = publish.package_product(files, 4, "Cost Guard")
    assert "index.html" in bundle and "main.html" not in bundle
    assert "PTP-004" in bundle["index.html"]  # attribution badge injected
    assert bundle["index.html"].index("PTP-004") < bundle["index.html"].index("</body>")
    assert "app.js" in bundle
    assert "schema.sql" not in bundle


def test_package_product_requires_html():
    with pytest.raises(publish.PublishError):
        publish.package_product([_file("Logic", "app.js", "x")], 4, "Thing")


def test_consolidate_components_merges_browser_language_groups():
    from p2pops.build.scoring import consolidate_components

    components = [
        ComponentSpec(name="Page", responsibility="markup", tech="HTML page"),
        ComponentSpec(name="Calculator", responsibility="score", tech="JavaScript logic"),
        ComponentSpec(name="Tracker", responsibility="history", tech="JavaScript logic", key_interfaces=["track()"]),
        ComponentSpec(name="Style", responsibility="design", tech="CSS stylesheet"),
        ComponentSpec(name="Backend", responsibility="api", tech="FastAPI service"),
    ]
    result = consolidate_components(components)
    names = [c.name for c in result]
    assert names == ["Page", "Calculator", "Style", "Backend"]  # JS pair merged, others untouched
    merged = result[1]
    assert "score" in merged.responsibility and "history" in merged.responsibility
    assert "track()" in merged.key_interfaces


def test_ensure_browser_components_injects_missing_page():
    from p2pops.build.scoring import ensure_browser_components

    browser_slate = [
        ComponentSpec(name="Logic", responsibility="score", tech="JavaScript logic"),
        ComponentSpec(name="Style", responsibility="design", tech="CSS stylesheet"),
    ]
    result = ensure_browser_components(browser_slate)
    assert [c.name for c in result] == ["HTML Page", "Logic", "Style"]

    non_browser = [ComponentSpec(name="API", responsibility="api", tech="FastAPI service")]
    assert [c.name for c in ensure_browser_components(non_browser)] == ["API"]


def test_undefined_dom_ids_audit():
    from p2pops.build.scoring import undefined_dom_ids

    html = ScaffoldFile(
        component="Page",
        path="index.html",
        language="html",
        content='<div id="score"></div><input id="name-field">',
    )
    js = ScaffoldFile(
        component="Logic",
        path="app.js",
        language="javascript",
        content="document.getElementById('score'); document.querySelector('#missing-panel'); getElementById(\"name-field\")",
    )
    assert undefined_dom_ids([html, js]) == ["missing-panel"]
    js_ok = ScaffoldFile(component="L", path="app.js", language="javascript", content="getElementById('score')")
    assert undefined_dom_ids([html, js_ok]) == []


def test_link_assets_injects_missing_references_only():
    from p2pops.build.scoring import link_assets

    html = ScaffoldFile(
        component="Page",
        path="index.html",
        language="html",
        content='<html><head><link rel="stylesheet" href="styles.css"></head><body></body></html>',
    )
    css = ScaffoldFile(component="Style", path="styles.css", language="css", content="body{}")
    js = ScaffoldFile(component="Logic", path="app.js", language="javascript", content="init()")
    files = link_assets([html, css, js])
    content = files[0].content
    assert content.count("styles.css") == 1  # already referenced — not duplicated
    assert '<script src="app.js" defer></script>' in content
    assert content.index("app.js") < content.index("</body>")


def test_product_slug_is_bounded_and_clean():
    assert publish.product_slug(4, "Cost Guard!") == "ptp-004-cost-guard"
    long = publish.product_slug(12, "A" * 100)
    assert len(long) <= 48 and long.startswith("ptp-012-")


# --- Publish stage in the build graph (offline) ---------------------------------------


async def test_build_graph_publishes_on_qa_pass(db, monkeypatch):
    from test_build import run_build

    monkeypatch.setenv("VERCEL_TOKEN", "test-token")
    get_settings.cache_clear()

    async def fake_publish(files, ptp_number, product_name):
        assert ptp_number == 7
        return f"https://ptp-{ptp_number:03d}-fake.vercel.app"

    monkeypatch.setattr(publish, "publish_product", fake_publish)
    try:
        _, build = await run_build(monkeypatch, qa_rounds_to_clean=1, ptp_number=7)
    finally:
        get_settings.cache_clear()

    import json

    build_row = await repo.get_build(build.id)
    assert build_row.status == "complete"
    assert build_row.deploy_url == "https://ptp-007-fake.vercel.app"
    assert json.loads(build_row.dossier)["deploy_url"] == "https://ptp-007-fake.vercel.app"


async def test_build_graph_skips_publish_without_credentials(db, monkeypatch):
    from test_build import run_build

    # Blank (not delenv): the developer's .env may carry a real token, and a
    # blank env var wins over .env then normalizes to None via the validator.
    monkeypatch.setenv("VERCEL_TOKEN", "")
    get_settings.cache_clear()
    try:
        run, build = await run_build(monkeypatch, qa_rounds_to_clean=1, ptp_number=7)
    finally:
        get_settings.cache_clear()

    build_row = await repo.get_build(build.id)
    assert build_row.status == "complete"
    assert build_row.deploy_url is None
    events = await repo.events_after(run.id)
    assert any("publish skipped" in e.message for e in events)


# --- Public keyword search -------------------------------------------------------------


@pytest.fixture
async def client(db, monkeypatch):
    async def fake_resume(run_id: str) -> bool:
        return not await repo.pending_reviews(run_id)

    monkeypatch.setattr(runner, "maybe_resume_after_decision", fake_resume)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def search_stubs(monkeypatch):
    """Guardrail allows everything; start_run records instead of running."""
    started: list[tuple[str, str | None]] = []

    async def fake_allowed(keyword: str) -> bool:
        return "forbidden" not in keyword

    async def fake_start_run(topic: str, source: str = "operator", keyword: str | None = None):
        run = await repo.create_run(topic, source=source, keyword=keyword)
        started.append((topic, keyword))
        return run

    monkeypatch.setattr(app_module, "is_search_query_allowed", fake_allowed)
    monkeypatch.setattr(runner, "start_run", fake_start_run)
    return started


async def test_search_starts_scoped_run_and_returns_matches(client, search_stubs):
    run = await repo.create_run("seed")
    await repo.save_idea(make_idea("shortlisted", title="Agent eval drift"), run_id=run.id)

    res = await client.post("/api/v1/search", json={"keyword": "agent eval"})
    assert res.status_code == 200
    body = res.json()
    assert body["outcome"] == "started"
    assert body["run_id"] is not None
    assert [m["title"] for m in body["matches"]] == ["Agent eval drift"]
    assert search_stubs == [("agent eval — real developer / AI-engineering pain points", "agent eval")]

    run_detail = (await client.get(f"/api/v1/runs/{body['run_id']}")).json()
    assert run_detail["source"] == "search"
    assert run_detail["keyword"] == "agent eval"


async def test_search_dedupes_recent_keyword(client, search_stubs):
    first = await client.post("/api/v1/search", json={"keyword": "Prompt Caching"})
    second = await client.post("/api/v1/search", json={"keyword": "prompt   caching"})
    assert second.json()["outcome"] == "deduplicated"
    assert second.json()["run_id"] == first.json()["run_id"]
    assert len(search_stubs) == 1


async def test_search_guardrail_blocks(client, search_stubs):
    res = await client.post("/api/v1/search", json={"keyword": "forbidden topic"})
    assert res.json()["outcome"] == "blocked"
    assert search_stubs == []


async def test_search_per_client_rate_limit(client, search_stubs, monkeypatch):
    monkeypatch.setenv("SEARCH_REQUESTS_PER_HOUR_PER_CLIENT", "1")
    get_settings.cache_clear()
    try:
        first = await client.post("/api/v1/search", json={"keyword": "token budgets"})
        assert first.json()["outcome"] == "started"
        second = await client.post("/api/v1/search", json={"keyword": "another topic"})
        assert second.json()["outcome"] == "rate_limited"
    finally:
        get_settings.cache_clear()
    assert len(search_stubs) == 1


async def test_search_daily_cost_ceiling_blocks_runs(client, search_stubs, monkeypatch):
    await repo.record_llm_call("venture/validator", "groq", "m", 10, 10, 5.0)
    monkeypatch.setenv("DAILY_COST_CEILING_USD", "1.0")
    get_settings.cache_clear()
    try:
        res = await client.post("/api/v1/search", json={"keyword": "expensive topic"})
        assert res.json()["outcome"] == "budget_exhausted"
    finally:
        get_settings.cache_clear()
    assert search_stubs == []


# --- Console approval queue ---------------------------------------------------------


async def test_pending_reviews_and_json_decision_flow(client):
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea("shortlisted"), run_id=run.id)
    review = await repo.create_review(run.id, idea.id)

    pending = (await client.get("/api/v1/reviews/pending")).json()
    assert [p["token"] for p in pending] == [review.id]
    assert pending[0]["idea"]["id"] == idea.id

    decided = await client.post(f"/api/v1/reviews/{review.id}", json={"decision": "approve"})
    assert decided.status_code == 200
    assert decided.json() == {"decision": "approved", "run_resumed": True}

    # Token consumed: queue is empty and a second decision is refused.
    assert (await client.get("/api/v1/reviews/pending")).json() == []
    again = await client.post(f"/api/v1/reviews/{review.id}", json={"decision": "reject"})
    assert again.status_code == 410


async def test_pending_reviews_requires_operator_token_when_configured(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret123")
    get_settings.cache_clear()
    try:
        assert (await client.get("/api/v1/reviews/pending")).status_code == 401
        ok = await client.get(
            "/api/v1/reviews/pending", headers={"Authorization": "Bearer secret123"}
        )
        assert ok.status_code == 200
    finally:
        get_settings.cache_clear()


# --- Showcase API ---------------------------------------------------------------------


async def test_showcase_endpoints(client):
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea("shortlisted", title="Visible problem"), run_id=run.id)

    items = (await client.get("/api/v1/showcase")).json()
    assert len(items) == 1
    assert items[0]["ptp_number"] == idea.ptp_number
    assert items[0]["stage"] == "validated"

    detail = (await client.get(f"/api/v1/showcase/{idea.ptp_number}")).json()
    assert detail["title"] == "Visible problem"
    assert (await client.get("/api/v1/showcase/999")).status_code == 404
