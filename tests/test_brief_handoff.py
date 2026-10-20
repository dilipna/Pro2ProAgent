"""Real HTTP/SQLite boundaries, without model calls, email or publication."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import update

from p2pops import guardrails, runner
from p2pops.api.app import app
from p2pops.briefs import ProblemBrief, digest
from p2pops.config import get_settings
from p2pops.db import repository as repo
from p2pops.db.engine import session
from p2pops.db.models import Idea

EXAMPLE = json.loads((Path(__file__).parents[1] / "contracts/problem-brief.v1.example.json").read_text())


@pytest.fixture
async def client(db):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.parametrize(
    "output,expected",
    [
        ({}, False),
        ({"allowed": "true"}, False),
        ({"allowed": 1}, False),
        ({"allowed": False}, False),
        ({"allowed": True}, True),
        (None, False),
    ],
)
async def test_only_an_explicit_boolean_guardrail_allow_can_authorize(output, expected):
    class Rail:
        async def generate_async(self, **kwargs):
            return SimpleNamespace(output_data=output)

    if not isinstance(output, dict) or type(output.get("allowed")) is not bool:
        with pytest.raises(guardrails.GuardrailDecisionError):
            await guardrails._check(Rail(), "a problem")
    else:
        assert await guardrails._check(Rail(), "a problem") is expected


async def test_missing_operator_credentials_deny_access_even_with_production_bypass(client, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_LOCAL_OPERATOR_BYPASS", "true")
    get_settings.cache_clear()
    assert (await client.post("/api/v1/briefs/import", json=EXAMPLE)).status_code == 503


async def test_import_review_and_missing_model_execution_are_real_and_idempotent(client):
    first = (await client.post("/api/v1/briefs/import", json=EXAMPLE)).json()
    second = (await client.post("/api/v1/briefs/import", json=EXAMPLE)).json()
    assert first["created"] and not second["created"]
    assert first["run_id"] == second["run_id"]
    url = f"/api/v1/briefs/{first['run_id']}"
    inspection = (await client.get(url)).json()
    assert inspection["status"] == "awaiting_review"
    review = inspection["pending"][0]
    assert review["snapshot"]["brief"]["source"]["evidence"] == EXAMPLE["source"]["evidence"]
    assert (
        await client.post(f"/api/v1/reviews/{review['token']}", json={"decision": "approve"})
    ).status_code == 409
    response = await client.post(
        f"/api/v1/reviews/{review['token']}",
        json={"decision": "approve", "snapshot_sha256": review["snapshot_sha256"]},
    )
    assert response.status_code == 200
    inspection = (await client.get(url)).json()
    assert inspection["status"] == "ready_to_build"
    approved = inspection["ideas"][0]["approved_snapshot"]
    assert digest(approved["content"]) == approved["sha256"]
    assert approved["content"]["brief"]["spec"]["acceptance"] == EXAMPLE["spec"]["acceptance"]
    assert (await client.post(url + "/execute")).status_code == 503
    assert (await client.get(url)).json()["status"] == "ready_to_build"


async def test_changed_idea_cannot_use_an_old_approval(db):
    run, idea, review, _ = await repo.import_brief(ProblemBrief.model_validate(EXAMPLE))
    async with session() as s:
        await s.execute(update(Idea).where(Idea.id == idea.id).values(title="Different scope"))
        await s.commit()
    assert await repo.record_decision(review.id, "approved", review.snapshot_sha256) is None
    assert (await repo.get_run(run.id)).status == "awaiting_review"


async def test_simultaneous_decisions_and_resume_claim_launch_at_most_once(db):
    run, idea, review, _ = await repo.import_brief(ProblemBrief.model_validate(EXAMPLE))
    decisions = await asyncio.gather(
        repo.record_decision(review.id, "approved"), repo.record_decision(review.id, "rejected")
    )
    assert sum(r is not None for r in decisions) == 1
    claims = await asyncio.gather(repo.claim_resume(run.id), repo.claim_resume(run.id))
    assert sum(claims) == 1


async def test_scanning_approval_links_and_unconfirmed_posts_change_nothing(client):
    run, idea, review, _ = await repo.import_brief(ProblemBrief.model_validate(EXAMPLE))
    for _ in range(2):
        assert (await client.get(f"/r/{review.id}/approve")).status_code == 200
    assert (await repo.get_idea(idea.id)).status == "shortlisted"
    assert (await client.post(f"/r/{review.id}/approve", data={"confirmation": "forged"})).status_code == 403
    assert (await repo.get_review(review.id)).decision == "pending"


async def test_rejection_and_duplicate_submit_do_not_build(client, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("No build should run")

    monkeypatch.setattr(runner, "execute_build", forbidden)
    run, idea, review, _ = await repo.import_brief(ProblemBrief.model_validate(EXAMPLE))
    endpoint = f"/api/v1/reviews/{review.id}"
    assert (await client.post(endpoint, json={"decision": "reject"})).status_code == 200
    assert (await repo.get_run(run.id)).status == "declined"
    assert (await client.post(endpoint, json={"decision": "reject"})).status_code == 410
    assert not await repo.claim_brief_execution(run.id)


async def test_unknown_and_malformed_evidence_never_imports(client):
    bad = json.loads(json.dumps(EXAMPLE))
    bad["source"]["evidence"] = []
    assert (await client.post("/api/v1/briefs/import", json=bad)).status_code == 422
    bad = json.loads(json.dumps(EXAMPLE))
    bad["source"]["evidence"][0]["url"] = "javascript:alert(1)"
    assert (await client.post("/api/v1/briefs/import", json=bad)).status_code == 422


async def test_approved_evidence_reaches_venture_and_build_dossiers(db, monkeypatch):
    from p2pops.build.graph import build_build_graph
    from p2pops.venture import agents
    from p2pops.venture.schemas import OpportunityDossier
    from test_build import build_fake_structured as build_outputs
    from test_venture import build_fake_structured as venture_outputs
    from test_venture import fake_evidence

    run, idea, review, _ = await repo.import_brief(ProblemBrief.model_validate(EXAMPLE))
    await repo.record_decision(review.id, "approved")
    idea = await repo.get_idea(idea.id)
    expected = await repo.approved_snapshot(idea.id)
    original = venture_outputs(problem_is_real=True, stress_rounds_to_clean=1)
    seen = []

    async def structured(schema, prompt, **kwargs):
        seen.append(prompt)
        return await original(schema, prompt, **kwargs)

    monkeypatch.setattr(agents, "_structured", structured)
    monkeypatch.setattr(agents, "gather_evidence", fake_evidence)
    opportunity_id = await runner.execute_venture(run.id, idea)
    opportunity = await repo.get_opportunity(opportunity_id)
    dossier = OpportunityDossier.model_validate_json(opportunity.dossier)
    assert dossier.approved_snapshot == expected
    assert any(EXAMPLE["source"]["evidence"][0]["excerpt"] in p for p in seen)
    monkeypatch.setattr(agents, "_structured", build_outputs(qa_rounds_to_clean=1))

    async def completion(*args, **kwargs):
        return "// deterministic test artifact"

    monkeypatch.setattr(agents, "_completion", completion)
    build = await repo.create_build(run.id, opportunity.id)
    await (
        build_build_graph()
        .compile()
        .ainvoke(
            {
                "run_id": run.id,
                "build_id": build.id,
                "opportunity_id": opportunity.id,
                "dossier": dossier,
                "ptp_number": 7,
            }
        )
    )
    stored = await repo.get_build(build.id)
    assert json.loads(stored.dossier)["approved_snapshot"] == expected
    assert stored.deploy_url is None
    assert any("requires independent functional checks" in e.message for e in await repo.events_after(run.id))


async def test_artifact_acceptance_requires_complete_checks_and_the_current_hash(client):
    from p2pops.briefs import artifact_digest

    run, idea, review, _ = await repo.import_brief(ProblemBrief.model_validate(EXAMPLE))
    await repo.record_decision(review.id, "approved")
    approved = await repo.approved_snapshot(idea.id)
    opportunity = await repo.create_opportunity(run.id, idea.id)
    build = await repo.create_build(run.id, opportunity.id)
    dossier = {
        "approved_snapshot": approved,
        "scaffold_files": [{"path": "index.html", "content": "<h1>Review queue</h1>"}],
    }
    await repo.finish_build(build.id, "complete", json.dumps(dossier))
    payload = {
        "artifact_sha256": artifact_digest(dossier),
        "decision": "accept",
        "method": "Synthetic test observations; not a real browser evaluation",
        "checks": [{"criterion": i, "passed": True, "observation": "test fixture check"} for i in range(3)],
    }
    endpoint = f"/api/v1/builds/{build.id}/accept"
    assert (await client.post(endpoint, json={**payload, "artifact_sha256": "0" * 64})).status_code == 409
    assert (await client.post(endpoint, json={**payload, "checks": payload["checks"][:1]})).status_code == 409
    failed = json.loads(json.dumps(payload))
    failed["checks"][0]["passed"] = False
    assert (await client.post(endpoint, json=failed)).status_code == 409
    assert (await client.post(endpoint, json=payload)).json()["published"] is False
    assert (await repo.get_run(run.id)).status == "accepted"
    assert (await client.post(endpoint, json=payload)).status_code == 409


async def test_import_body_limit_is_enforced_before_parsing(client):
    response = await client.post("/api/v1/briefs/import", content="x" * 64001)
    assert response.status_code == 413


def test_browser_schema_and_example_match_the_backend_contract():
    schema = json.loads((Path(__file__).parents[1] / "contracts/problem-brief.v1.schema.json").read_text())
    assert schema == ProblemBrief.model_json_schema()
    browser = Path(__file__).parents[1] / "web/src/data"
    assert json.loads((browser / "problem-brief.v1.schema.json").read_text()) == schema
    assert json.loads((browser / "brief-example.json").read_text()) == EXAMPLE
