"""Run lifecycle: start, execute, pause at the human gate, resume.

Owns the compiled graph + AsyncSqliteSaver checkpointer for the process.
The checkpointer is what makes the email HITL real: the graph thread
(thread_id == run_id) survives process restarts between "review requested"
and the reviewer's click.
"""

import asyncio
import json
import logging
from pathlib import Path

import logfire
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from .build.graph import build_build_graph
from .config import get_settings
from .db import repository as repo
from .db.models import Build, Idea, Run
from .graph import build_pipeline_graph
from .venture.graph import build_venture_graph
from .venture.schemas import OpportunityDossier

logger = logging.getLogger(__name__)

_checkpointer_cm = None
_pipeline = None
_venture = None
_build = None
_lock = asyncio.Lock()


async def get_pipeline():
    global _checkpointer_cm, _pipeline
    async with _lock:
        if _pipeline is None:
            settings = get_settings()
            Path(settings.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
            _checkpointer_cm = AsyncSqliteSaver.from_conn_string(settings.checkpoint_db_path)
            checkpointer = await _checkpointer_cm.__aenter__()
            _pipeline = build_pipeline_graph().compile(checkpointer=checkpointer)
        return _pipeline


def get_venture_pipeline():
    """The venture graph is stateless between steps (no human gate inside),
    so it compiles without a checkpointer."""
    global _venture
    if _venture is None:
        _venture = build_venture_graph().compile()
    return _venture


def get_build_pipeline():
    """Same as the venture graph: stateless, no checkpointer needed."""
    global _build
    if _build is None:
        _build = build_build_graph().compile()
    return _build


async def shutdown_pipeline() -> None:
    global _checkpointer_cm, _pipeline, _venture, _build
    async with _lock:
        if _checkpointer_cm is not None:
            await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
        _pipeline = None
        _venture = None
        _build = None


def _run_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


async def execute_run(run_id: str, topic: str) -> None:
    """Drives a run until it completes or pauses at the human gate."""
    try:
        pipeline = await get_pipeline()
        with logfire.span("run.execute", run_id=run_id, topic=topic):
            result = await pipeline.ainvoke(
                {"run_id": run_id, "topic": topic}, _run_config(run_id)
            )
        if "__interrupt__" in result:
            logger.info("Run %s paused at the human gate", run_id)
    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        await repo.add_event(run_id, "system", "error", str(exc))
        await repo.set_run_status(run_id, "failed", str(exc))


async def start_run(topic: str) -> Run:
    """Creates the run record and executes the pipeline in the background."""
    run = await repo.create_run(topic)
    asyncio.create_task(execute_run(run.id, topic))
    return run


async def execute_venture(run_id: str, idea: Idea) -> None:
    """Runs the venture pipeline for one approved idea, recording into the
    same run timeline. Failures are contained per-idea."""
    opportunity = await repo.create_opportunity(run_id, idea.id)
    try:
        venture = get_venture_pipeline()
        with logfire.span("venture.execute", run_id=run_id, idea_id=idea.id):
            await venture.ainvoke(
                {
                    "run_id": run_id,
                    "opportunity_id": opportunity.id,
                    "idea_id": idea.id,
                    "title": idea.title,
                    "description": idea.description,
                    "reasoning": idea.reasoning or "",
                }
            )
    except Exception as exc:
        logger.exception("Venture pipeline failed for idea %s", idea.id)
        await repo.add_event(run_id, "venture/system", "error", f"{idea.title[:60]}: {exc}")
        await repo.finish_opportunity(opportunity.id, "failed", "")


def _build_ready_dossier(opportunity) -> OpportunityDossier:
    if opportunity.status != "complete" or not opportunity.dossier:
        raise ValueError(
            f"opportunity {opportunity.id} is not build-ready "
            f"(status={opportunity.status!r}); build-squad requires a complete dossier"
        )
    return OpportunityDossier.model_validate(json.loads(opportunity.dossier))


async def _run_build_graph(run_id: str, build_id: str, opportunity_id: str, dossier: OpportunityDossier) -> None:
    """Invokes the compiled build-squad graph against an already-created
    Build row. Contains failures the same way execute_venture does: one
    bad build never corrupts the opportunity or the run."""
    try:
        pipeline = get_build_pipeline()
        with logfire.span("build.execute", run_id=run_id, opportunity_id=opportunity_id):
            await pipeline.ainvoke(
                {"run_id": run_id, "build_id": build_id, "opportunity_id": opportunity_id, "dossier": dossier}
            )
    except Exception as exc:
        logger.exception("Build-squad failed for opportunity %s", opportunity_id)
        await repo.add_event(run_id, "build/system", "error", f"{dossier.idea_title[:60]}: {exc}")
        await repo.finish_build(build_id, "failed", "")


async def start_build(opportunity_id: str) -> Build:
    """Validates the opportunity, creates the Build row, launches the
    graph in the background, and returns immediately -- mirrors
    `start_run`/`create_run`. Used by the protected `POST /api/v1/builds`
    endpoint; never wired to a public frontend button."""
    opportunity = await repo.get_opportunity(opportunity_id)
    if opportunity is None:
        raise ValueError(f"no such opportunity: {opportunity_id}")
    dossier = _build_ready_dossier(opportunity)
    build = await repo.create_build(opportunity.run_id, opportunity_id)
    asyncio.create_task(_run_build_graph(opportunity.run_id, build.id, opportunity_id, dossier))
    return build


async def execute_build(opportunity_id: str) -> Build:
    """Validates the opportunity, creates the Build row, and runs the
    graph to completion before returning -- manually triggered, never
    automatic (unlike venture pipeline after human approval). Used by the
    `p2pops-build` CLI, which blocks until done so it can print the
    result; no HTTP round trip needed."""
    opportunity = await repo.get_opportunity(opportunity_id)
    if opportunity is None:
        raise ValueError(f"no such opportunity: {opportunity_id}")
    dossier = _build_ready_dossier(opportunity)
    build = await repo.create_build(opportunity.run_id, opportunity_id)
    await _run_build_graph(opportunity.run_id, build.id, opportunity_id, dossier)
    return await repo.get_build(build.id)


async def resume_run(run_id: str) -> None:
    """Resumes a paused run with the recorded human decisions, then drives
    every approved idea through the venture pipeline."""
    decisions = await repo.decisions_for_run(run_id)
    try:
        pipeline = await get_pipeline()
        with logfire.span("run.resume", run_id=run_id, decisions=len(decisions)):
            await pipeline.ainvoke(Command(resume=decisions), _run_config(run_id))
    except Exception as exc:
        logger.exception("Resume of run %s failed", run_id)
        await repo.add_event(run_id, "system", "error", f"resume failed: {exc}")
        await repo.set_run_status(run_id, "failed", str(exc))
        return

    approved_ids = [idea_id for idea_id, decision in decisions.items() if decision == "approved"]
    if not approved_ids:
        return

    run = await repo.get_run(run_id)
    ideas = [i for i in (run.ideas if run else []) if i.id in set(approved_ids)]
    await repo.set_run_status(run_id, "building")
    # Sequential on purpose: caps LLM spend/concurrency and keeps the event
    # timeline readable. Parallelism here is a knob, not a rewrite.
    for idea in ideas:
        await execute_venture(run_id, idea)
    await repo.set_run_status(run_id, "completed")


async def maybe_resume_after_decision(run_id: str) -> bool:
    """Called after each recorded decision; resumes once none are pending."""
    pending = await repo.pending_reviews(run_id)
    if pending:
        return False
    asyncio.create_task(resume_run(run_id))
    return True
