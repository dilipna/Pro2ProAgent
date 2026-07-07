"""End-to-end build-squad graph tests, offline.

Same approach as test_venture.py: the shared `_structured` seam
(`p2pops.venture.agents._structured`) is replaced with a deterministic
fake, so the whole orchestration -- PM -> Architect -> Engineer fan-out ->
QA gate -> bounded revise loop -- runs exactly as in production, minus
network and cost. Patching it on `venture_agents` (not on
`p2pops.build.agents`) is itself the proof that build/agents.py's
module-attribute-access import (`venture_agents._structured(...)`, not
`from ..venture.agents import _structured`) actually works -- if that
import style were wrong, these tests would silently try to call a real
LLM instead of the fake.
"""

import json

from conftest import make_idea
from p2pops.build.graph import build_build_graph
from p2pops.build.schemas import (
    ArchitectureSpec,
    BuildPlan,
    ComponentSpec,
    DataEntity,
    DataField,
    DataModel,
    QAIssue,
    QAReport,
    ScaffoldContent,
    StackChoice,
)
from p2pops.db import repository as repo
from p2pops.venture import agents as venture_agents
from p2pops.venture.schemas import EvidenceBundle, OpportunityDossier, ProductVision

COMPONENTS = ("API Service", "Web Console")


def build_fake_structured(*, qa_rounds_to_clean: int, critical_component: str = "API Service"):
    """Returns a `_structured` stand-in with scenario knobs."""
    qa_calls = {"n": 0}

    async def fake(schema, prompt, *, agent, tier="default", max_tokens=2048):
        if schema is BuildPlan:
            return BuildPlan(
                features=[
                    {
                        "name": "Core loop",
                        "description": "run the wedge end to end",
                        "priority": "P0",
                        "acceptance_criteria": ["a request completes"],
                    }
                ],
                tech_stack=[StackChoice(layer="backend", choice="FastAPI", rationale="fast, typed")],
                non_goals=["multi-tenant auth"],
            )
        if schema is ArchitectureSpec:
            return ArchitectureSpec(
                components=[
                    ComponentSpec(
                        name="API Service",
                        responsibility="serves the core loop",
                        tech="FastAPI service",
                        key_interfaces=["POST /run"],
                    ),
                    ComponentSpec(
                        name="Web Console",
                        responsibility="operator UI",
                        tech="Next.js frontend",
                        key_interfaces=["/console"],
                    ),
                ],
                data_model=DataModel(entities=[DataEntity(name="Run", fields=[DataField(name="id", type="str")])]),
                api_surface=["POST /run"],
                rationale="two components suffice for v1",
            )
        if schema is ScaffoldContent:
            for name in COMPONENTS:
                if f"COMPONENT: {name}" in prompt:
                    return ScaffoldContent(
                        content=f"# scaffold for {name}\n# TODO: implement",
                        key_decisions=[f"{name}: minimal v1 stub"],
                    )
            raise AssertionError(f"unexpected component prompt: {prompt[:200]}")
        if schema is QAReport:
            qa_calls["n"] += 1
            if qa_calls["n"] >= qa_rounds_to_clean:
                return QAReport(issues=[], verdict="approved", reasoning="scaffold matches the plan")
            return QAReport(
                issues=[
                    QAIssue(
                        component=critical_component,
                        severity="critical",
                        issue="missing P0 route",
                        fix="add the POST /run handler",
                    )
                ],
                verdict="needs_revision",
                reasoning="scaffold doesn't yet cover the P0 feature",
            )
        raise AssertionError(f"unexpected schema {schema}")

    return fake


async def run_build(monkeypatch, *, qa_rounds_to_clean: int = 1, critical_component: str = "API Service"):
    monkeypatch.setattr(
        venture_agents,
        "_structured",
        build_fake_structured(qa_rounds_to_clean=qa_rounds_to_clean, critical_component=critical_component),
    )

    run = await repo.create_run("test topic")
    idea_row = await repo.save_idea(make_idea("approved"), run_id=run.id)
    opportunity = await repo.create_opportunity(run.id, idea_row.id)

    dossier_in = OpportunityDossier(
        idea_id=idea_row.id,
        idea_title=idea_row.title,
        status="complete",
        evidence=EvidenceBundle(query="q", items=[]),
        chosen_direction="FlightRecorder",
        vision=ProductVision(
            product_name="FlightRecorder",
            one_liner="Black-box recorder for AI agents.",
            value_proposition="Explains agent failures in minutes, not days.",
            positioning="Forensics, not dashboards.",
            differentiation=["causal traces"],
            target_segment="platform teams",
            execution_strategy="wedge: postmortems",
            success_metrics=["time-to-root-cause < 10 min"],
            known_risks=[],
        ),
    )
    await repo.finish_opportunity(opportunity.id, "complete", dossier_in.model_dump_json())

    build = await repo.create_build(run.id, opportunity.id)
    graph = build_build_graph().compile()
    await graph.ainvoke(
        {
            "run_id": run.id,
            "build_id": build.id,
            "opportunity_id": opportunity.id,
            "dossier": dossier_in,
        }
    )
    return run, build


async def test_clean_pass_first_round(db, monkeypatch):
    run, build = await run_build(monkeypatch, qa_rounds_to_clean=1)

    b = await repo.get_build(build.id)
    assert b.status == "complete"

    dossier = json.loads(b.dossier)
    assert dossier["status"] == "complete"
    assert dossier["product_name"] == "FlightRecorder"
    assert len(dossier["qa_reports"]) == 1
    assert len(dossier["scaffold_files"]) == 2
    assert [g["gate"] for g in dossier["gates"]] == ["qa-round-1"]
    assert dossier["gates"][0]["passed"] is True

    events = await repo.events_after(run.id)
    agents_seen = {e.agent for e in events}
    assert {"build/pm", "build/architect", "build/engineer", "build/qa", "build/gate", "build/system"} <= agents_seen
    # One event per component, not one summary event for the whole fan-out.
    engineer_events = [e for e in events if e.agent == "build/engineer"]
    assert len(engineer_events) == 2


async def test_one_revision_round_then_clean(db, monkeypatch):
    run, build = await run_build(monkeypatch, qa_rounds_to_clean=2, critical_component="API Service")

    b = await repo.get_build(build.id)
    assert b.status == "complete"

    dossier = json.loads(b.dossier)
    assert len(dossier["qa_reports"]) == 2
    assert [g["gate"] for g in dossier["gates"]] == ["qa-round-1", "qa-round-2"]
    assert [g["passed"] for g in dossier["gates"]] == [False, True]
    # Revised file replaces the original for that component, not duplicates.
    assert len(dossier["scaffold_files"]) == 2


async def test_exhausted_revision_yields_needs_revision(db, monkeypatch):
    # QA never comes back clean -> the bounded loop must surface
    # needs_revision honestly, not silently accept or loop forever.
    run, build = await run_build(monkeypatch, qa_rounds_to_clean=99)

    b = await repo.get_build(build.id)
    assert b.status == "needs_revision"

    dossier = json.loads(b.dossier)
    assert dossier["status"] == "needs_revision"
    assert len(dossier["qa_reports"]) == 2  # MAX_QA_ROUNDS=1 -> initial + one revision round


async def test_unmatched_component_name_falls_back_to_revising_all(db, monkeypatch):
    # QA names a component that doesn't exist in the architecture -- must
    # not silently no-op; should redo every component instead.
    run, build = await run_build(monkeypatch, qa_rounds_to_clean=2, critical_component="Nonexistent Component")

    b = await repo.get_build(build.id)
    assert b.status == "complete"

    events = await repo.events_after(run.id)
    fallback_events = [e for e in events if "unknown component" in e.message]
    assert len(fallback_events) == 1
