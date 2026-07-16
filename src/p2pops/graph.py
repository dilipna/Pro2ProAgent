"""The ProToPro pipeline graph.

research -> analyst -> request_review -> human_gate -> finalize

Every node records RunEvents (the AgentOps timeline the console renders).
The human gate uses LangGraph's interrupt(): the graph genuinely pauses,
the reviewer decides over email (ADR-0002), and the API resumes the thread
with the decisions.

Side effects (creating review tokens, sending the email) live in
`request_review`, a separate node *before* the interrupt — on resume,
LangGraph re-executes the interrupted node from its top, so `human_gate`
must contain nothing but the interrupt call.
"""

import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import notify
from .agents.analyst import analyze_idea
from .agents.research import run_research
from .db import repository as repo
from .memory import remember
from .models import DiscoveredIdea


class PipelineState(TypedDict, total=False):
    run_id: str
    topic: str
    ideas: list[dict]  # DiscoveredIdea dumps (checkpointer-friendly)
    shortlisted_ids: list[str]  # persisted Idea ids awaiting human review
    status_counts: dict[str, int]
    decisions: dict[str, str]  # idea_id -> approved | rejected


async def research_node(state: PipelineState) -> dict:
    run_id = state["run_id"]
    await repo.add_event(run_id, "research", "stage_started", f"topic: {state['topic']}")
    t0 = time.monotonic()

    report = await run_research(state["topic"])

    duration_ms = (time.monotonic() - t0) * 1000
    for idea in report.ideas:
        await repo.add_event(run_id, "research", "idea_discovered", idea.title)
    await repo.add_event(
        run_id,
        "research",
        "stage_completed",
        f"{len(report.ideas)} candidate problems",
        duration_ms=duration_ms,
    )
    return {"ideas": [idea.model_dump() for idea in report.ideas]}


def route_after_research(state: PipelineState) -> str:
    return "analyst" if state.get("ideas") else "finalize"


async def analyst_node(state: PipelineState) -> dict:
    run_id = state["run_id"]
    await repo.add_event(run_id, "analyst", "stage_started", f"{len(state['ideas'])} ideas to vet")
    t0 = time.monotonic()

    shortlisted_ids: list[str] = []
    counts: dict[str, int] = {}
    for raw in state["ideas"]:
        idea = DiscoveredIdea.model_validate(raw)
        analyzed = await analyze_idea(idea)
        row = await repo.save_idea(analyzed, run_id=run_id)

        counts[analyzed.status] = counts.get(analyzed.status, 0) + 1
        if analyzed.status != "duplicate":
            remember(row.id, f"{analyzed.title}\n{analyzed.description}")
        if analyzed.status == "shortlisted":
            shortlisted_ids.append(row.id)

        detail = f"[{analyzed.status}] score={analyzed.score} {analyzed.title}"
        await repo.add_event(run_id, "analyst", "idea_analyzed", detail)

    duration_ms = (time.monotonic() - t0) * 1000
    await repo.add_event(
        run_id, "analyst", "stage_completed", str(counts), duration_ms=duration_ms
    )
    return {"shortlisted_ids": shortlisted_ids, "status_counts": counts}


def route_after_analyst(state: PipelineState) -> str:
    return "request_review" if state.get("shortlisted_ids") else "finalize"


async def request_review_node(state: PipelineState) -> dict:
    """Creates single-use review tokens and emails the human gate."""
    run_id = state["run_id"]
    run = await repo.get_run(run_id)
    assert run is not None

    ideas = [i for i in run.ideas if i.id in set(state["shortlisted_ids"])]
    reviews = {idea.id: await repo.create_review(run_id, idea.id) for idea in ideas}

    emailed = await notify.send_review_request(run, ideas, reviews)
    await repo.set_run_status(run_id, "awaiting_review")
    detail = (
        f"{len(ideas)} ideas sent for review"
        if emailed
        else f"{len(ideas)} ideas awaiting review — email delivery failed, approve via the console queue"
    )
    await repo.add_event(run_id, "human-gate", "review_requested", detail)
    return {}


async def human_gate_node(state: PipelineState) -> dict:
    # Nothing but the interrupt: this node re-executes from the top on resume.
    decisions = interrupt(
        {"run_id": state["run_id"], "awaiting": len(state.get("shortlisted_ids", []))}
    )
    return {"decisions": decisions or {}}


async def finalize_node(state: PipelineState) -> dict:
    run_id = state["run_id"]
    decisions = state.get("decisions") or {}
    for idea_id, decision in decisions.items():
        await repo.add_event(run_id, "human-gate", "review_decided", f"{decision}: {idea_id}")

    summary = state.get("status_counts") or {}
    approved = sum(1 for d in decisions.values() if d == "approved")
    message = f"analysis {summary}" + (f" · approved for build: {approved}" if decisions else "")
    await repo.add_event(run_id, "system", "stage_completed", message)
    await repo.set_run_status(run_id, "completed")
    return {}


def build_pipeline_graph() -> StateGraph:
    graph = StateGraph(PipelineState)
    graph.add_node("research", research_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("request_review", request_review_node)
    graph.add_node("human_gate", human_gate_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "research")
    graph.add_conditional_edges(
        "research", route_after_research, {"analyst": "analyst", "finalize": "finalize"}
    )
    graph.add_conditional_edges(
        "analyst",
        route_after_analyst,
        {"request_review": "request_review", "finalize": "finalize"},
    )
    graph.add_edge("request_review", "human_gate")
    graph.add_edge("human_gate", "finalize")
    graph.add_edge("finalize", END)
    return graph
