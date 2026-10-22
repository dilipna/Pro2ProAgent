"""Checkpointed execution of approved imported briefs on one persistent host.

Only this path has the recovery contract. Legacy discovery remains unchanged.
The kernel owns per-job exclusion; SQLite owns job/stage identities and results.
"""

import asyncio
import logging

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .build.graph import build_build_graph
from .config import get_settings
from .db import executions as jobs
from .db import repository as repo
from .execution_identity import execution_fingerprint
from .process_lock import execution_lock
from .venture.graph import build_venture_graph
from .venture.schemas import OpportunityDossier

logger = logging.getLogger(__name__)


async def _invoke(graph, store, thread: str, inputs: dict) -> None:
    pipeline = graph.compile(checkpointer=store)
    config = {"configurable": {"thread_id": thread}}
    saved = await pipeline.aget_state(config)
    # Sync persistence completes a checkpoint before scheduling its next step.
    await pipeline.ainvoke(None if saved.created_at else inputs, config, durability="sync")


async def _approved(job) -> dict:
    if job.code_fingerprint != execution_fingerprint():
        raise ValueError("Execution code/runtime changed; checkpoint recovery requires operator review")
    snapshot = await repo.approved_snapshot(job.idea_id)
    if snapshot is None or snapshot["sha256"] != job.approval_sha256:
        raise ValueError("Original approval is missing or changed; execution refused")
    idea = await repo.get_idea(job.idea_id)
    if idea is None or idea.status != "approved":
        raise ValueError("Idea is no longer approved; execution refused")
    return snapshot


async def process_job(run_id: str) -> str:
    """Return busy/deferred/complete/failed without ever publishing a product."""
    # One worker across all imported-brief jobs on this persistent host, even
    # when multiple API processes accidentally share its DATA_DIR.
    with execution_lock("0" * 32) as acquired:
        if not acquired:
            return "busy"
        job = await jobs.get_job(run_id)
        if job is None or job.status in ("complete", "failed"):
            return "absent" if job is None else job.status
        if not get_settings().active_api_key:
            return "deferred"
        await jobs.begin_attempt(run_id)
        try:
            snapshot = await _approved(job)
            idea = await repo.get_idea(job.idea_id)
            async with AsyncSqliteSaver.from_conn_string(get_settings().checkpoint_db_path) as store:
                opportunity = await repo.get_opportunity(job.opportunity_id)
                if opportunity is None:
                    raise ValueError("Persisted opportunity is missing")
                if opportunity.status == "validating":
                    await _invoke(
                        build_venture_graph(),
                        store,
                        f"brief:{run_id}:venture",
                        {
                            "run_id": run_id,
                            "opportunity_id": job.opportunity_id,
                            "idea_id": job.idea_id,
                            "title": idea.title,
                            "description": idea.description,
                            "reasoning": idea.reasoning or "",
                            "approved_snapshot": snapshot,
                        },
                    )
                opportunity = await repo.get_opportunity(job.opportunity_id)
                if opportunity.status in ("rejected", "parked"):
                    await jobs.conclude(run_id, opportunity.status)
                    return "complete"
                if opportunity.status != "complete" or not opportunity.dossier:
                    raise ValueError("Venture did not produce a completed dossier")
                dossier = OpportunityDossier.model_validate_json(opportunity.dossier)
                if dossier.approved_snapshot != snapshot:
                    raise ValueError("Venture output does not match the approved input")
                await _approved(job)
                build_id = await jobs.ensure_build(run_id)
                build = await repo.get_build(build_id)
                if build.status == "scaffolding":
                    await _invoke(
                        build_build_graph(),
                        store,
                        f"brief:{run_id}:build",
                        {
                            "run_id": run_id,
                            "build_id": build_id,
                            "opportunity_id": job.opportunity_id,
                            "dossier": dossier,
                            "ptp_number": idea.ptp_number,
                        },
                    )
                build = await repo.get_build(build_id)
                if build.status not in ("complete", "needs_revision") or not build.dossier:
                    raise ValueError("Build did not produce a durable artifact")
                await _approved(job)
                outcome = "awaiting_acceptance" if build.status == "complete" else "needs_revision"
                await jobs.conclude(run_id, outcome)
                return "complete"
        except Exception as exc:
            logger.exception("Durable execution %s failed", run_id)
            await jobs.conclude(run_id, "failed", str(exc))
            await repo.add_event(run_id, "execution", "error", str(exc))
            return "failed"


async def worker_loop() -> None:
    """Sequential, bounded-concurrency worker. Cancellation leaves jobs resumable."""
    while True:
        try:
            for run_id in await jobs.pending_jobs():
                await process_job(run_id)
        except Exception:
            logger.exception("Durable worker scan failed; persisted jobs remain queued")
            await asyncio.sleep(5)
        await asyncio.sleep(1)
