"""End-to-end venture graph tests, offline.

The `_structured` seam is replaced with a deterministic fake, so the whole
orchestration — parallel fan-out, gates, the refine loop, dossier
persistence — runs exactly as in production, minus network and cost.
"""

import json

from conftest import make_idea
from p2pops.db import repository as repo
from p2pops.venture import agents
from p2pops.venture.graph import build_venture_graph
from p2pops.venture.schemas import (
    CompetitorLandscape,
    DemandAssessment,
    DirectionSlate,
    EvidenceBundle,
    EvidenceItem,
    ExistingSolution,
    ProblemValidation,
    ProductVision,
    RefinedDirection,
    SegmentAnalysis,
    SolutionDirection,
    StressIssue,
    StressTestReport,
    UserSegment,
)


def build_fake_structured(*, problem_is_real: bool, stress_rounds_to_clean: int):
    """Returns a `_structured` stand-in with scenario knobs."""
    stress_calls = {"n": 0}

    async def fake(schema, prompt, *, agent, tier="default", max_tokens=2048):
        if schema is ProblemValidation:
            return ProblemValidation(
                is_real=problem_is_real,
                recurrence=70,
                importance=80,
                evidence_summary="Grounded in E1, E2.",
                confidence=0.85,
            )
        if schema is SegmentAnalysis:
            return SegmentAnalysis(
                segments=[
                    UserSegment(name="platform teams", motivation="fewer incidents", current_workaround="scripts", reachability=70),
                    UserSegment(name="solo builders", motivation="ship faster", current_workaround="none", reachability=50),
                ],
                primary_segment="platform teams",
                confidence=0.8,
            )
        if schema is DemandAssessment:
            return DemandAssessment(
                urgency=75,
                frequency=80,
                willingness_to_pay=60,
                demand_signals=["teams already pay for partial fixes (E1)"],
                market_size_reasoning="thousands of teams run agents in prod",
                confidence=0.8,
            )
        if schema is CompetitorLandscape:
            return CompetitorLandscape(
                solutions=[ExistingSolution(name="ToolX", approach="dashboards", shortcoming="no cause analysis")],
                unserved_gap="explain WHY an agent failed, not just that it failed",
                saturation=40,
                confidence=0.75,
            )
        if schema is DirectionSlate:
            return DirectionSlate(
                directions=[
                    SolutionDirection(
                        name="FlightRecorder",
                        approach="always-on causal trace",
                        principle="own-the-system-of-record",
                        wedge="postmortems for agent incidents",
                        problem_fit=90,
                        feasibility=80,
                        differentiation=70,
                        monetization_path=80,
                        key_risk="trace volume cost",
                    ),
                    SolutionDirection(
                        name="WeakerIdea",
                        approach="generic dashboard",
                        principle="composable-primitives",
                        wedge="graphs",
                        problem_fit=50,
                        feasibility=70,
                        differentiation=30,
                        monetization_path=40,
                        key_risk="me-too",
                    ),
                ],
                rejected_framings=["chatbot over logs — no durable value"],
            )
        if schema is StressTestReport:
            stress_calls["n"] += 1
            if stress_calls["n"] >= stress_rounds_to_clean:
                return StressTestReport(issues=[], verdict="proceed", reasoning="mitigations hold")
            return StressTestReport(
                issues=[
                    StressIssue(
                        lens="financial",
                        severity="critical",
                        issue="trace storage costs exceed revenue at scale",
                        mitigation="tiered retention",
                    )
                ],
                verdict="proceed_with_mitigations",
                reasoning="cost model unproven",
            )
        if schema is RefinedDirection:
            return RefinedDirection(
                revised_approach="causal trace with tiered retention",
                revised_wedge="postmortems for agent incidents",
                changes_made=["tiered retention answers the storage-cost critical"],
                issues_unresolved=[],
            )
        if schema is ProductVision:
            return ProductVision(
                product_name="FlightRecorder",
                one_liner="Black-box recorder for AI agents.",
                value_proposition="Explains agent failures in minutes, not days.",
                positioning="Forensics, not dashboards.",
                differentiation=["causal traces", "system of record"],
                target_segment="platform teams",
                execution_strategy="wedge: postmortems; channel: OSS SDK",
                success_metrics=["time-to-root-cause < 10 min"],
                known_risks=[],
            )
        raise AssertionError(f"unexpected schema {schema}")

    return fake


async def fake_evidence(title: str, description: str) -> EvidenceBundle:
    return EvidenceBundle(
        query=title,
        items=[EvidenceItem(source="hackernews", title="thread", url="https://hn.example", detail="500 points")],
    )


async def run_venture(monkeypatch, *, problem_is_real=True, stress_rounds_to_clean=2):
    monkeypatch.setattr(
        agents, "_structured", build_fake_structured(
            problem_is_real=problem_is_real, stress_rounds_to_clean=stress_rounds_to_clean
        )
    )
    monkeypatch.setattr(agents, "gather_evidence", fake_evidence)

    run = await repo.create_run("test topic")
    idea_row = await repo.save_idea(make_idea("approved"), run_id=run.id)
    opportunity = await repo.create_opportunity(run.id, idea_row.id)

    graph = build_venture_graph().compile()
    await graph.ainvoke(
        {
            "run_id": run.id,
            "opportunity_id": opportunity.id,
            "idea_id": idea_row.id,
            "title": idea_row.title,
            "description": idea_row.description,
            "reasoning": idea_row.reasoning or "",
        }
    )
    return run, opportunity


async def test_happy_path_with_one_refinement_round(db, monkeypatch):
    run, opportunity = await run_venture(monkeypatch, stress_rounds_to_clean=2)

    opp = await repo.get_opportunity(opportunity.id)
    assert opp.status == "complete"

    dossier = json.loads(opp.dossier)
    assert dossier["chosen_direction"] == "FlightRecorder"
    assert dossier["vision"]["product_name"] == "FlightRecorder"
    # Round 1 failed the stress gate, refine ran, round 2 passed:
    assert len(dossier["stress_reports"]) == 2
    assert len(dossier["refinements"]) == 1
    gate_names = [g["gate"] for g in dossier["gates"]]
    assert gate_names == ["validation", "direction", "stress-round-1", "stress-round-2"]
    assert [g["passed"] for g in dossier["gates"]] == [True, True, False, True]

    # The full journey is on the run's event timeline.
    events = await repo.events_after(run.id)
    agents_seen = {e.agent for e in events}
    assert {"venture/validator", "venture/architect", "venture/red-team", "venture/refiner",
            "venture/strategist", "venture/gate", "venture/system"} <= agents_seen


async def test_unreal_problem_is_rejected_before_solutioning(db, monkeypatch):
    run, opportunity = await run_venture(monkeypatch, problem_is_real=False)

    opp = await repo.get_opportunity(opportunity.id)
    assert opp.status == "rejected"

    dossier = json.loads(opp.dossier)
    assert dossier["slate"] is None  # never reached the architect
    assert dossier["vision"] is None
    validation_gate = next(g for g in dossier["gates"] if g["gate"] == "validation")
    assert not validation_gate["passed"]


async def test_exhausted_refinements_park_the_opportunity(db, monkeypatch):
    # Stress never comes back clean -> bounded loop must park, not spin.
    run, opportunity = await run_venture(monkeypatch, stress_rounds_to_clean=99)

    opp = await repo.get_opportunity(opportunity.id)
    assert opp.status == "parked"

    dossier = json.loads(opp.dossier)
    assert len(dossier["stress_reports"]) == 2  # MAX_REFINEMENT_ROUNDS
    assert dossier["vision"] is None
