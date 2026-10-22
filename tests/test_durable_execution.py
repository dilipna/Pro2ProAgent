"""Durable job state must survive actual startup orphan handling."""

import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select, text, update

from p2pops import durable, runner
from p2pops.api.app import app
from p2pops.briefs import ProblemBrief, artifact_digest
from p2pops.config import get_settings
from p2pops.db import executions as jobs
from p2pops.db import repository as repo
from p2pops.db.engine import get_engine, init_db, session
from p2pops.db.models import Build, ExecutionJob, Idea, Opportunity

EXAMPLE = json.loads((Path(__file__).parents[1] / "contracts/problem-brief.v1.example.json").read_text())


async def approved_job():
    run, idea, review, _ = await repo.import_brief(ProblemBrief.model_validate(EXAMPLE))
    await repo.record_decision(review.id, "approved")
    assert await runner.maybe_resume_after_decision(run.id)
    assert await repo.claim_brief_execution(run.id)
    return run, idea


async def test_claimed_approved_work_survives_startup(db):
    run, _ = await approved_job()
    await repo.fail_orphaned_runs()
    assert (await repo.get_run(run.id)).status == "building"


def launch(run_id, root, pause="", suffix="worker"):
    env = dict(
        os.environ,
        DATA_DIR=str(root),
        PTP_TEST_PAUSE=pause,
        ANTHROPIC_API_KEY="fixture-not-a-real-key",
        LLM_PROVIDER="anthropic",
        GROQ_API_KEY="",
        OPENROUTER_API_KEY="",
        VERCEL_TOKEN="",
        RESEND_API_KEY="",
        LANGSMITH_API_KEY="",
        LOGFIRE_TOKEN="",
        HF_HUB_OFFLINE="1",
        LITELLM_LOCAL_MODEL_COST_MAP="True",
        XPLOREMORE_API_URL="",
    )
    log = (root / f"{suffix}.log").open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).with_name("durable_worker_fixture.py")), run_id],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    finally:
        log.close()
    return process


async def wait_at_barrier(process, root):
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        if (root / "paused.json").exists():
            return
        assert process.poll() is None, (root / "first.log").read_text(encoding="utf-8")
        await asyncio.sleep(0.05)
    raise AssertionError("Worker never reached the kill barrier")


def calls(root):
    path = root / "fixture-calls.jsonl"
    return [json.loads(line)["label"] for line in path.read_text().splitlines()] if path.exists() else []


@pytest.mark.parametrize(
    "point",
    [
        "before_worker",
        "venture:ProductVision",
        "after_venture",
        "build:QAReport",
        "before_complete",
    ],
)
async def test_process_death_recovers_real_graphs_with_stable_identities(db, point):
    run, idea = await approved_job()
    root = Path(get_settings().data_dir)
    initial = await jobs.get_job(run.id)
    child = launch(run.id, root, point, "first")
    try:
        await wait_at_barrier(child, root)
        recorded = calls(root)
        at_kill = await jobs.get_job(run.id)
        old_build = await repo.get_build(at_kill.build_id) if at_kill.build_id else None
        old_artifact = old_build.dossier if old_build and old_build.status == "complete" else None
        # Prove contention against a live owner, before releasing its lock.
        if point == "build:QAReport":
            rival = launch(run.id, root, suffix="rival")
            assert await asyncio.to_thread(rival.wait, timeout=100) == 0
            assert '"result": "busy"' in (root / "rival.log").read_text()
            assert calls(root) == recorded
    finally:
        if child.poll() is None:
            child.kill()
        await asyncio.to_thread(child.wait, timeout=10)
    await repo.fail_orphaned_runs()
    assert (await repo.get_run(run.id)).status == "building"
    recovered = launch(run.id, root, suffix="recovered")
    try:
        assert await asyncio.to_thread(recovered.wait, timeout=100) == 0
    finally:
        if recovered.poll() is None:
            recovered.kill()
            recovered.wait(timeout=10)
    final = await jobs.get_job(run.id)
    log = (root / "recovered.log").read_text(encoding="utf-8")
    assert final.status == "complete", log
    assert (await repo.get_run(run.id)).status == "awaiting_acceptance"
    assert final.opportunity_id == initial.opportunity_id
    assert at_kill.build_id is None or final.build_id == at_kill.build_id
    artifact = await repo.get_build(final.build_id)
    assert artifact.deploy_url is None
    assert json.loads(artifact.dossier)["approved_snapshot"] == await repo.approved_snapshot(idea.id)
    if old_artifact is not None:
        assert artifact.dossier == old_artifact
        assert calls(root) == recorded  # complete artifact was not regenerated
    if point != "before_worker":
        assert calls(root).count("venture:evidence") == 1
    if point in ("build:QAReport", "before_complete"):
        assert calls(root).count("build:file") == recorded.count("build:file")
    async with session() as s:
        assert await s.scalar(select(func.count()).select_from(ExecutionJob)) == 1
        assert await s.scalar(select(func.count()).select_from(Opportunity)) == 1
        assert await s.scalar(select(func.count()).select_from(Build)) == 1
    with sqlite3.connect(get_settings().checkpoint_db_path) as connection:
        checkpoints = connection.execute(
            "SELECT thread_id, count(*) FROM checkpoints GROUP BY thread_id"
        ).fetchall()
    receipt = {
        "scenario": point,
        "run_id": run.id,
        "opportunity_id": final.opportunity_id,
        "build_id": final.build_id,
        "approval_sha256": final.approval_sha256,
        "execution_fingerprint": final.code_fingerprint,
        "killed_process_exit": child.returncode,
        "recovered_process_exit": recovered.returncode,
        "attempts": final.attempts,
        "calls_before_kill": recorded,
        "calls_after_recovery": calls(root),
        "checkpoint_counts": dict(checkpoints),
        "final_run_status": "awaiting_acceptance",
        "artifact_dossier_sha256": hashlib.sha256(artifact.dossier.encode()).hexdigest(),
        "artifact_sha256": artifact_digest(json.loads(artifact.dossier)),
        "event_count": len((await repo.get_run(run.id)).events),
        "live_model_calls": 0,
        "generated_products_published": 0,
        "limits": "Deterministic model boundaries; restart orchestration only, not product quality or exactly-once billing.",
    }
    (root / "recovery-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


async def test_changed_approval_stops_recovery_before_any_model_boundary(db, monkeypatch):
    run, idea = await approved_job()
    async with session() as s:
        await s.execute(update(Idea).where(Idea.id == idea.id).values(description="changed"))
        await s.commit()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-not-real")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()
    assert await durable.process_job(run.id) == "failed"
    assert "changed" in (await jobs.get_job(run.id)).error.lower()
    assert (await repo.get_opportunity((await jobs.get_job(run.id)).opportunity_id)).dossier is None


async def test_missing_provider_leaves_job_queued_and_unconsumed(db, monkeypatch):
    run, _ = await approved_job()
    for key in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    assert await durable.process_job(run.id) == "deferred"
    job = await jobs.get_job(run.id)
    assert job.status == "queued" and job.attempts == 0


async def test_duplicate_http_execution_atomically_admits_one_job(db, monkeypatch):
    run, _, review, _ = await repo.import_brief(ProblemBrief.model_validate(EXAMPLE))
    await repo.record_decision(review.id, "approved")
    assert await runner.maybe_resume_after_decision(run.id)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-not-real")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(*(client.post(f"/api/v1/briefs/{run.id}/execute") for _ in range(5)))
        assert sorted(r.status_code for r in responses) == [202, 409, 409, 409, 409]
        inspection = await client.get(f"/api/v1/briefs/{run.id}/execution")
        assert inspection.status_code == 200
        assert inspection.json()["status"] == "queued"
    async with session() as s:
        assert await s.scalar(select(func.count()).select_from(ExecutionJob)) == 1
        assert await s.scalar(select(func.count()).select_from(Opportunity)) == 1
        assert await s.scalar(select(func.count()).select_from(Build)) == 0


async def test_graph_error_is_visible_and_not_automatically_retried(db, monkeypatch):
    run, _ = await approved_job()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-not-real")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()
    attempts = []

    async def broken(*args, **kwargs):
        attempts.append(True)
        raise ValueError("deliberate fixture graph failure")

    monkeypatch.setattr(durable, "_invoke", broken)
    assert await durable.process_job(run.id) == "failed"
    assert await durable.process_job(run.id) == "failed"
    job = await jobs.get_job(run.id)
    assert job.attempts == 1 and len(attempts) == 1
    assert "deliberate fixture" in job.error
    assert run.id not in await jobs.pending_jobs()
    assert (await repo.get_run(run.id)).status == "failed"


async def test_changed_runtime_requires_review_before_graph_execution(db, monkeypatch):
    run, _ = await approved_job()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-not-real")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()
    monkeypatch.setattr(durable, "execution_fingerprint", lambda: "different-code")
    assert await durable.process_job(run.id) == "failed"
    assert "code/runtime changed" in (await jobs.get_job(run.id)).error
    assert (await repo.get_opportunity((await jobs.get_job(run.id)).opportunity_id)).dossier is None


async def test_uninterrupted_control_uses_the_same_production_worker(db):
    run, _ = await approved_job()
    root = Path(get_settings().data_dir)
    child = launch(run.id, root, suffix="control")
    try:
        assert await asyncio.to_thread(child.wait, timeout=100) == 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
    job = await jobs.get_job(run.id)
    assert job.status == "complete" and job.attempts == 1
    assert (await repo.get_run(run.id)).status == "awaiting_acceptance"
    trajectory = calls(root)
    assert trajectory.count("venture:evidence") == 1
    # Assert causal ordering, allowing independent analysis nodes to vary.
    for before, after in [
        ("venture:evidence", "venture:ProblemValidation"),
        ("venture:DemandAssessment", "venture:ProblemValidation"),
        ("venture:CompetitorLandscape", "venture:ProblemValidation"),
        ("venture:SegmentAnalysis", "venture:ProblemValidation"),
        ("venture:ProblemValidation", "venture:DirectionSlate"),
        ("venture:DirectionSlate", "venture:StressTestReport"),
        ("venture:StressTestReport", "venture:ProductVision"),
        ("venture:ProductVision", "build:BuildPlan"),
        ("build:BuildPlan", "build:ArchitectureSpec"),
        ("build:ArchitectureSpec", "build:file"),
        ("build:file", "build:QAReport"),
    ]:
        assert trajectory.index(before) < trajectory.index(after)
    assert (await repo.get_build(job.build_id)).deploy_url is None


async def test_additive_job_table_preserves_legacy_rows_and_orphan_policy(db):
    legacy = await repo.create_run("Pre-recovery discovery record")
    # Model an installed pre-release schema: all prior tables, no job table.
    async with get_engine().begin() as connection:
        await connection.execute(text("DROP TABLE execution_jobs"))
    await init_db()
    await init_db()  # migration is safe on subsequent startup
    assert (await repo.get_run(legacy.id)).topic == "Pre-recovery discovery record"
    run, _ = await approved_job()
    await repo.fail_orphaned_runs()
    assert (await repo.get_run(legacy.id)).status == "failed"
    assert (await repo.get_run(run.id)).status == "building"
    assert (await jobs.get_job(run.id)).status == "queued"
