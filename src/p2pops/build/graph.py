"""The build-squad graph -- runs once per manually-triggered
`p2pops-build <opportunity_id>` call.

    pm -> architect -> engineer -> qa -> [conditional]
                                     |
                    passed ----------+--- mark_complete -----> finish
                    failed & round < MAX_QA_ROUNDS -> revise -> qa (loop back)
                    failed & rounds exhausted -> mark_needs_revision -> finish

Design invariants (mirroring venture/graph.py):
- LLM agents produce artifacts; *code* makes the qa_gate pass/fail decision
  and every scaffold file's path/language (never asked of the LLM).
- Every node appends a RunEvent; Engineer's fan-out logs once per
  component, not one summary event, keeping AgentOps granularity
  consistent with every other stage.
- One component's LLM failure never aborts the whole build
  (asyncio.gather(..., return_exceptions=True)) -- the same per-item
  containment guarantee runner.execute_venture already provides at the
  idea level, extended down into a single node's internal fan-out.
- The revision loop is bounded (MAX_QA_ROUNDS=1) and honestly surfaces
  `needs_revision` rather than silently accepting or looping forever.
"""

import asyncio
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ..db import repository as repo
from ..venture.schemas import OpportunityDossier
from . import agents, scoring
from .schemas import (
    ArchitectureSpec,
    BuildDossier,
    BuildPlan,
    ComponentSpec,
    GateResult,
    QAReport,
    ScaffoldFile,
)


class BuildState(TypedDict, total=False):
    run_id: str
    build_id: str
    opportunity_id: str
    dossier: OpportunityDossier  # the input -- a *complete* venture dossier

    ctx: str
    plan: BuildPlan
    architecture: ArchitectureSpec
    scaffold_files: list[ScaffoldFile]
    qa_reports: list[QAReport]
    gates: list[GateResult]
    round_index: int
    outcome: str  # complete | needs_revision


async def _event(state: BuildState, agent: str, event_type: str, message: str, t0: float | None = None) -> None:
    duration_ms = (time.monotonic() - t0) * 1000 if t0 is not None else None
    await repo.add_event(state["run_id"], agent, event_type, message, duration_ms=duration_ms)


# --- Nodes ----------------------------------------------------------------------


async def pm_node(state: BuildState) -> dict:
    dossier = state["dossier"]
    if dossier.status != "complete" or dossier.vision is None:
        raise ValueError(
            "build-squad requires a complete OpportunityDossier with a vision; "
            f"got status={dossier.status!r}, vision={'set' if dossier.vision else 'None'}"
        )
    t0 = time.monotonic()
    ctx = agents._build_context(dossier)
    plan = await agents.write_plan(ctx)
    await _event(
        state, "build/pm", "stage_completed", f"{len(plan.features)} features · {len(plan.tech_stack)} stack choices", t0
    )
    return {"ctx": ctx, "plan": plan, "qa_reports": [], "gates": [], "round_index": 0}


async def architect_node(state: BuildState) -> dict:
    t0 = time.monotonic()
    architecture = await agents.design_architecture(state["ctx"], state["plan"])
    await _event(state, "build/architect", "stage_completed", f"{len(architecture.components)} components", t0)
    return {"architecture": architecture}


async def _run_engineer(
    state: BuildState,
    components: list[ComponentSpec],
    feedback_by_component: dict[str, str] | None = None,
) -> list[ScaffoldFile]:
    """Fans out one LLM call per component via asyncio.gather. Deliberately
    not LangGraph's Send/map-reduce API: this codebase never uses Send,
    the fan-out is bounded/known-at-runtime/non-recursive, and a single
    node collecting gather() results into one plain dict return needs no
    reducer fields -- Send would add a second orchestration primitive for
    zero behavioral benefit here."""
    feedback_by_component = feedback_by_component or {}

    async def _one(component: ComponentSpec) -> ScaffoldFile:
        t0 = time.monotonic()
        content = await agents.write_scaffold(
            state["ctx"],
            state["plan"],
            state["architecture"],
            component,
            feedback_by_component.get(component.name, ""),
        )
        path, language = scoring.scaffold_target(component)
        await _event(state, "build/engineer", "stage_completed", f"{component.name} -> {path}", t0)
        return ScaffoldFile(
            component=component.name,
            path=path,
            language=language,
            content=content.content,
            key_decisions=content.key_decisions,
        )

    results = await asyncio.gather(*(_one(c) for c in components), return_exceptions=True)
    files: list[ScaffoldFile] = []
    for component, result in zip(components, results, strict=True):
        if isinstance(result, Exception):
            await _event(state, "build/engineer", "error", f"{component.name}: {result}")
            continue
        files.append(result)
    return files


async def engineer_node(state: BuildState) -> dict:
    files = await _run_engineer(state, state["architecture"].components)
    return {"scaffold_files": files}


async def qa_node(state: BuildState) -> dict:
    t0 = time.monotonic()
    report = await agents.review_scaffold(state["ctx"], state["plan"], state["architecture"], state["scaffold_files"])
    round_index = state["round_index"] + 1
    gate = scoring.qa_gate(report, round_index)
    await _event(
        state,
        "build/qa",
        "stage_completed",
        f"round {round_index}: {report.verdict} · {len(report.issues)} issues ({len(report.critical_issues)} critical)",
        t0,
    )
    await _event(
        state,
        "build/gate",
        "gate_passed" if gate.passed else "gate_failed",
        f"qa gate round {round_index}: {'pass' if gate.passed else '; '.join(gate.reasons)}",
    )
    return {
        "qa_reports": state["qa_reports"] + [report],
        "gates": state["gates"] + [gate],
        "round_index": round_index,
    }


def route_after_qa(state: BuildState) -> str:
    if state["gates"][-1].passed:
        return "mark_complete"
    if state["round_index"] < scoring.MAX_QA_ROUNDS:
        return "revise"
    return "mark_needs_revision"


async def revise_node(state: BuildState) -> dict:
    report = state["qa_reports"][-1]
    components = state["architecture"].components
    known_names = {c.name for c in components}
    critical = report.critical_issues
    flagged_names = {issue.component for issue in critical}
    unmatched = flagged_names - known_names

    if unmatched or not flagged_names:
        # Either QA named a component that doesn't exist, or the gate
        # failed on verdict alone with no component-specific critical
        # issue to target -- in both cases there's no safe specific
        # target, so redo every component rather than silently no-op.
        reason = (
            f"QA named unknown component(s) {sorted(unmatched)}"
            if unmatched
            else "QA verdict failed with no component-specific critical issue"
        )
        await _event(state, "build/gate", "gate_failed", f"{reason} -- revising all components as a safe fallback")
        to_revise = components
    else:
        to_revise = [c for c in components if c.name in flagged_names]

    feedback_by_component: dict[str, list[str]] = {}
    for issue in critical:
        feedback_by_component.setdefault(issue.component, []).append(f"{issue.issue} (fix: {issue.fix})")
    feedback: dict[str, str] = {k: " / ".join(v) for k, v in feedback_by_component.items()}
    if not feedback:
        # No component-specific critical issues -- give every revised
        # component the overall QA reasoning so the round carries signal.
        feedback = {c.name: report.reasoning for c in to_revise}

    revised_files = await _run_engineer(state, to_revise, feedback)
    revised_by_name = {f.component: f for f in revised_files}
    merged = [revised_by_name.get(f.component, f) for f in state["scaffold_files"]]
    merged_names = {f.component for f in merged}
    merged.extend(f for f in revised_files if f.component not in merged_names)

    return {"scaffold_files": merged}


async def mark_complete_node(state: BuildState) -> dict:
    return {"outcome": "complete"}


async def mark_needs_revision_node(state: BuildState) -> dict:
    return {"outcome": "needs_revision"}


async def finish_node(state: BuildState) -> dict:
    outcome = state.get("outcome") or "needs_revision"
    dossier_in = state["dossier"]
    dossier = BuildDossier(
        opportunity_id=state["opportunity_id"],
        idea_title=dossier_in.idea_title,
        product_name=dossier_in.vision.product_name if dossier_in.vision else None,
        status=outcome,
        plan=state.get("plan"),
        architecture=state.get("architecture"),
        scaffold_files=state.get("scaffold_files") or [],
        qa_reports=state.get("qa_reports") or [],
        gates=state.get("gates") or [],
    )
    await repo.finish_build(state["build_id"], outcome, dossier.model_dump_json())
    await _event(state, "build/system", "stage_completed", f"build {outcome}: {dossier_in.idea_title[:80]}")
    return {}


def build_build_graph() -> StateGraph:
    graph = StateGraph(BuildState)
    graph.add_node("pm", pm_node)
    graph.add_node("architect", architect_node)
    graph.add_node("engineer", engineer_node)
    graph.add_node("qa", qa_node)
    graph.add_node("revise", revise_node)
    graph.add_node("mark_complete", mark_complete_node)
    graph.add_node("mark_needs_revision", mark_needs_revision_node)
    graph.add_node("finish", finish_node)

    graph.add_edge(START, "pm")
    graph.add_edge("pm", "architect")
    graph.add_edge("architect", "engineer")
    graph.add_edge("engineer", "qa")
    graph.add_conditional_edges(
        "qa",
        route_after_qa,
        {
            "mark_complete": "mark_complete",
            "revise": "revise",
            "mark_needs_revision": "mark_needs_revision",
        },
    )
    graph.add_edge("revise", "qa")
    graph.add_edge("mark_complete", "finish")
    graph.add_edge("mark_needs_revision", "finish")
    graph.add_edge("finish", END)
    return graph
