"""The venture pipeline graph — runs once per human-approved idea.

    evidence
       ├──> validate ──┐
       ├──> segments ──┤   (parallel fan-out)
       ├──> demand ────┤
       └──> landscape ─┘
              │
        validation_gate ── fail ──> finish(rejected)
              │
          directions ──> rank (deterministic) ── weak ──> finish(rejected)
              │
          stress ◄──────────┐
              │             │
         stress_gate ── refine (≤ MAX_REFINEMENT_ROUNDS)
              │  └── exhausted ──> finish(parked)
              │
            vision ──> finish(complete)

Design invariants:
- LLM agents produce artifacts; *code* makes decisions (ranking + gates).
- Every node appends to the run's event timeline; the terminal node persists
  the full dossier, so any outcome — including rejection — is reproducible
  and explainable after the fact.
- The refine loop is bounded and each round's report is kept, not
  overwritten: the dossier shows the argument, not just the conclusion.
"""

import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ..db import repository as repo
from . import agents, scoring
from .schemas import (
    CompetitorLandscape,
    DemandAssessment,
    DirectionSlate,
    EvidenceBundle,
    GateResult,
    OpportunityDossier,
    ProblemValidation,
    ProductVision,
    RankedDirection,
    RefinedDirection,
    SegmentAnalysis,
    StressTestReport,
)


class VentureState(TypedDict, total=False):
    run_id: str
    opportunity_id: str
    idea_id: str
    title: str
    description: str
    reasoning: str

    ctx: str
    evidence: EvidenceBundle
    validation: ProblemValidation
    segments: SegmentAnalysis
    demand: DemandAssessment
    landscape: CompetitorLandscape
    slate: DirectionSlate
    ranking: list[RankedDirection]
    stress_reports: list[StressTestReport]
    refinements: list[RefinedDirection]
    gates: list[GateResult]
    round_index: int
    vision: ProductVision
    outcome: str  # complete | rejected | parked


async def _event(state: VentureState, agent: str, event_type: str, message: str, t0: float | None = None) -> None:
    duration_ms = (time.monotonic() - t0) * 1000 if t0 is not None else None
    await repo.add_event(state["run_id"], agent, event_type, message, duration_ms=duration_ms)


# --- Nodes ----------------------------------------------------------------------


async def evidence_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    evidence = await agents.gather_evidence(state["title"], state["description"])
    ctx = agents._context(state["title"], state["description"], state["reasoning"], evidence)
    await _event(
        state, "venture/evidence", "stage_completed", f"{len(evidence.items)} evidence items", t0
    )
    return {"evidence": evidence, "ctx": ctx, "stress_reports": [], "refinements": [], "gates": [], "round_index": 0}


async def validate_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    validation = await agents.validate_problem(state["ctx"])
    await _event(
        state,
        "venture/validator",
        "stage_completed",
        f"real={validation.is_real} importance={validation.importance} conf={validation.confidence:.2f}",
        t0,
    )
    return {"validation": validation}


async def segments_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    segments = await agents.analyze_segments(state["ctx"])
    await _event(state, "venture/ethnographer", "stage_completed", f"primary: {segments.primary_segment}", t0)
    return {"segments": segments}


async def demand_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    demand = await agents.assess_demand(state["ctx"])
    await _event(
        state,
        "venture/demand-analyst",
        "stage_completed",
        f"urgency={demand.urgency} freq={demand.frequency} wtp={demand.willingness_to_pay}",
        t0,
    )
    return {"demand": demand}


async def landscape_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    landscape = await agents.scout_competitors(state["ctx"])
    await _event(
        state,
        "venture/competitor-scout",
        "stage_completed",
        f"{len(landscape.solutions)} solutions · saturation={landscape.saturation} · gap: {landscape.unserved_gap[:120]}",
        t0,
    )
    return {"landscape": landscape}


async def validation_gate_node(state: VentureState) -> dict:
    gate = scoring.validation_gate(state["validation"], state["demand"])
    await _event(
        state,
        "venture/gate",
        "gate_passed" if gate.passed else "gate_failed",
        f"validation gate: {'pass' if gate.passed else '; '.join(gate.reasons)}",
    )
    return {"gates": state["gates"] + [gate], "outcome": "" if gate.passed else "rejected"}


def route_after_validation_gate(state: VentureState) -> str:
    return "directions" if not state.get("outcome") else "finish"


async def directions_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    slate = await agents.generate_directions(
        state["ctx"], state["validation"], state["segments"], state["demand"], state["landscape"]
    )
    ranking = scoring.rank_directions(slate, state["landscape"])
    gate = scoring.direction_gate(ranking)

    top = ranking[0] if ranking else None
    summary = f"{len(slate.directions)} directions; top: {top.name} @ {top.composite}" if top else "no directions"
    await _event(state, "venture/architect", "stage_completed", summary, t0)
    await _event(
        state,
        "venture/gate",
        "gate_passed" if gate.passed else "gate_failed",
        f"direction gate: {'pass' if gate.passed else '; '.join(gate.reasons)}",
    )
    return {
        "slate": slate,
        "ranking": ranking,
        "gates": state["gates"] + [gate],
        "outcome": "" if gate.passed else "rejected",
    }


def route_after_directions(state: VentureState) -> str:
    return "stress" if not state.get("outcome") else "finish"


async def stress_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    direction = scoring.chosen(state["slate"], state["ranking"])
    latest_refinement = state["refinements"][-1] if state["refinements"] else None
    report = await agents.stress_test(state["ctx"], direction, latest_refinement)

    round_index = state["round_index"] + 1
    gate = scoring.stress_gate(report, round_index)
    await _event(
        state,
        "venture/red-team",
        "stage_completed",
        f"round {round_index}: {report.verdict} · {len(report.issues)} issues "
        f"({len(report.critical_issues)} critical)",
        t0,
    )
    return {
        "stress_reports": state["stress_reports"] + [report],
        "gates": state["gates"] + [gate],
        "round_index": round_index,
    }


def route_after_stress(state: VentureState) -> str:
    gate = state["gates"][-1]
    if gate.passed:
        return "vision"
    if state["round_index"] < scoring.MAX_REFINEMENT_ROUNDS:
        return "refine"
    return "park"


async def refine_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    direction = scoring.chosen(state["slate"], state["ranking"])
    report = state["stress_reports"][-1]
    refinement = await agents.refine_direction(state["ctx"], direction, report)
    await _event(
        state,
        "venture/refiner",
        "stage_completed",
        f"{len(refinement.changes_made)} changes · {len(refinement.issues_unresolved)} carried as risks",
        t0,
    )
    return {"refinements": state["refinements"] + [refinement]}


async def park_node(state: VentureState) -> dict:
    await _event(
        state,
        "venture/gate",
        "gate_failed",
        f"parked after {state['round_index']} stress rounds with unresolved critical issues",
    )
    return {"outcome": "parked"}


async def vision_node(state: VentureState) -> dict:
    t0 = time.monotonic()
    direction = scoring.chosen(state["slate"], state["ranking"])
    latest_refinement = state["refinements"][-1] if state["refinements"] else None
    unresolved = latest_refinement.issues_unresolved if latest_refinement else []
    vision = await agents.write_vision(
        state["ctx"], direction, state["segments"], state["landscape"], latest_refinement, unresolved
    )
    await _event(state, "venture/strategist", "stage_completed", f"vision: {vision.product_name} — {vision.one_liner}", t0)
    return {"vision": vision, "outcome": "complete"}


async def finish_node(state: VentureState) -> dict:
    outcome = state.get("outcome") or "rejected"
    dossier = OpportunityDossier(
        idea_id=state["idea_id"],
        idea_title=state["title"],
        status=outcome,
        evidence=state.get("evidence") or EvidenceBundle(query=""),
        validation=state.get("validation"),
        segments=state.get("segments"),
        demand=state.get("demand"),
        landscape=state.get("landscape"),
        slate=state.get("slate"),
        ranking=state.get("ranking") or [],
        chosen_direction=state["ranking"][0].name if state.get("ranking") else None,
        stress_reports=state.get("stress_reports") or [],
        refinements=state.get("refinements") or [],
        vision=state.get("vision"),
        gates=state.get("gates") or [],
    )
    await repo.finish_opportunity(state["opportunity_id"], outcome, dossier.model_dump_json())
    await _event(state, "venture/system", "stage_completed", f"opportunity {outcome}: {state['title'][:80]}")
    return {}


def build_venture_graph() -> StateGraph:
    graph = StateGraph(VentureState)
    graph.add_node("evidence", evidence_node)
    graph.add_node("validate", validate_node)
    graph.add_node("segments", segments_node)
    graph.add_node("demand", demand_node)
    graph.add_node("landscape", landscape_node)
    graph.add_node("validation_gate", validation_gate_node)
    graph.add_node("directions", directions_node)
    graph.add_node("stress", stress_node)
    graph.add_node("refine", refine_node)
    graph.add_node("park", park_node)
    graph.add_node("vision", vision_node)
    graph.add_node("finish", finish_node)

    graph.add_edge(START, "evidence")
    # Parallel analysis fan-out / fan-in.
    for analysis in ("validate", "segments", "demand", "landscape"):
        graph.add_edge("evidence", analysis)
        graph.add_edge(analysis, "validation_gate")
    graph.add_conditional_edges(
        "validation_gate", route_after_validation_gate, {"directions": "directions", "finish": "finish"}
    )
    graph.add_conditional_edges(
        "directions", route_after_directions, {"stress": "stress", "finish": "finish"}
    )
    graph.add_conditional_edges(
        "stress", route_after_stress, {"vision": "vision", "refine": "refine", "park": "park"}
    )
    graph.add_edge("refine", "stress")
    graph.add_edge("park", "finish")
    graph.add_edge("vision", "finish")
    graph.add_edge("finish", END)
    return graph
