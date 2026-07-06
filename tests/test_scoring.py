from p2pops.venture import scoring
from p2pops.venture.principles import PRINCIPLES
from p2pops.venture.schemas import (
    CompetitorLandscape,
    DemandAssessment,
    DirectionSlate,
    ProblemValidation,
    SolutionDirection,
    StressIssue,
    StressTestReport,
)


def direction(name: str, pf: int, mon: int, diff: int, feas: int) -> SolutionDirection:
    return SolutionDirection(
        name=name,
        approach="a",
        principle="collapse-integration-friction",
        wedge="w",
        problem_fit=pf,
        feasibility=feas,
        differentiation=diff,
        monetization_path=mon,
        key_risk="r",
    )


def landscape(saturation: int) -> CompetitorLandscape:
    return CompetitorLandscape(solutions=[], unserved_gap="gap", saturation=saturation, confidence=0.8)


def test_ranking_is_deterministic_and_weighted():
    slate = DirectionSlate(
        directions=[
            direction("weak", 40, 40, 40, 40),
            direction("strong", 90, 80, 70, 80),
        ]
    )
    ranking = scoring.rank_directions(slate, landscape(saturation=40))

    assert [r.name for r in ranking] == ["strong", "weak"]
    # 90*.30 + 80*.25 + 70*.25*(1-.5*.4) + 80*.20 = 27+20+14+16
    assert ranking[0].composite == 77.0
    assert ranking[0].breakdown["differentiation"] == 14.0


def test_saturation_damps_differentiation():
    slate = DirectionSlate(directions=[direction("d", 50, 50, 100, 50)])
    open_market = scoring.rank_directions(slate, landscape(0))[0].composite
    saturated = scoring.rank_directions(slate, landscape(100))[0].composite
    assert open_market > saturated


def test_validation_gate_rejects_unreal_and_weak_problems():
    demand = DemandAssessment(
        urgency=70, frequency=70, willingness_to_pay=50,
        demand_signals=[], market_size_reasoning="", confidence=0.8,
    )
    good = ProblemValidation(
        is_real=True, recurrence=70, importance=80,
        evidence_summary="", confidence=0.9,
    )
    assert scoring.validation_gate(good, demand).passed

    unreal = good.model_copy(update={"is_real": False})
    result = scoring.validation_gate(unreal, demand)
    assert not result.passed and result.reasons

    unimportant = good.model_copy(update={"importance": 30})
    assert not scoring.validation_gate(unimportant, demand).passed


def test_stress_gate_blocks_critical_issues():
    clean = StressTestReport(issues=[], verdict="proceed", reasoning="fine")
    assert scoring.stress_gate(clean, 1).passed

    critical = StressTestReport(
        issues=[StressIssue(lens="technical", severity="critical", issue="x", mitigation="none known")],
        verdict="proceed_with_mitigations",
        reasoning="risky",
    )
    assert not scoring.stress_gate(critical, 1).passed


def test_scores_clamp_out_of_range_values():
    d = direction("d", 150, -10, 50, 50)
    assert d.problem_fit == 100
    assert d.monetization_path == 0


def test_principles_library_integrity():
    keys = [p.key for p in PRINCIPLES]
    assert len(keys) == len(set(keys))
    assert len(PRINCIPLES) >= 6
    for p in PRINCIPLES:
        assert p.principle and p.when_applicable and p.failure_mode
