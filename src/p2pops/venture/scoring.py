"""Deterministic scoring and quality gates for the venture pipeline.

The LLM agents supply bounded sub-scores with cited reasoning; the actual
ranking and go/no-go decisions are computed here, in code — so two runs
over the same artifacts rank identically, and every decision has an
inspectable numeric breakdown. This is the line between "the model felt
like it" and an explainable pipeline.
"""

from .schemas import (
    CompetitorLandscape,
    DemandAssessment,
    DirectionSlate,
    GateResult,
    ProblemValidation,
    RankedDirection,
    SolutionDirection,
    StressTestReport,
)

# --- Direction ranking ---------------------------------------------------------

# Weights sum to 1.0. Demand-side signals (problem fit + monetization) carry
# the most weight: the classic failure mode of engineer-led ideas is
# building the feasible thing nobody urgently pays for.
DIRECTION_WEIGHTS: dict[str, float] = {
    "problem_fit": 0.30,
    "monetization_path": 0.25,
    "differentiation": 0.25,
    "feasibility": 0.20,
}

# Crowded markets tax differentiation-weak directions; computed as a
# multiplier on the differentiation component, not a blanket penalty.
SATURATION_DAMPING = 0.5  # at saturation=100, differentiation contributes 50%


def rank_directions(
    slate: DirectionSlate, landscape: CompetitorLandscape
) -> list[RankedDirection]:
    """Ranks directions by weighted composite, highest first. Deterministic."""
    saturation_factor = 1.0 - SATURATION_DAMPING * (landscape.saturation / 100.0)
    ranked = []
    for d in slate.directions:
        breakdown = {
            "problem_fit": d.problem_fit * DIRECTION_WEIGHTS["problem_fit"],
            "monetization_path": d.monetization_path * DIRECTION_WEIGHTS["monetization_path"],
            "differentiation": d.differentiation
            * DIRECTION_WEIGHTS["differentiation"]
            * saturation_factor,
            "feasibility": d.feasibility * DIRECTION_WEIGHTS["feasibility"],
        }
        ranked.append(
            RankedDirection(
                name=d.name,
                composite=round(sum(breakdown.values()), 2),
                breakdown={k: round(v, 2) for k, v in breakdown.items()},
            )
        )
    # Stable tie-break on name keeps ordering reproducible.
    return sorted(ranked, key=lambda r: (-r.composite, r.name))


def chosen(slate: DirectionSlate, ranking: list[RankedDirection]) -> SolutionDirection:
    top_name = ranking[0].name
    return next(d for d in slate.directions if d.name == top_name)


# --- Quality gates ---------------------------------------------------------------

MIN_VALIDATION_IMPORTANCE = 55
MIN_VALIDATION_CONFIDENCE = 0.55
MIN_DEMAND_URGENCY_OR_FREQUENCY = 45
MIN_DIRECTION_COMPOSITE = 60.0
MAX_REFINEMENT_ROUNDS = 2


def validation_gate(
    validation: ProblemValidation, demand: DemandAssessment
) -> GateResult:
    """Go/no-go after parallel analysis: is this worth solutioning at all?"""
    reasons = []
    if not validation.is_real:
        reasons.append("validator found no evidence of a real problem")
    if validation.importance < MIN_VALIDATION_IMPORTANCE:
        reasons.append(
            f"importance {validation.importance} < {MIN_VALIDATION_IMPORTANCE}"
        )
    if validation.confidence < MIN_VALIDATION_CONFIDENCE:
        reasons.append(
            f"validation confidence {validation.confidence:.2f} < {MIN_VALIDATION_CONFIDENCE}"
        )
    if max(demand.urgency, demand.frequency) < MIN_DEMAND_URGENCY_OR_FREQUENCY:
        reasons.append(
            f"neither urgency ({demand.urgency}) nor frequency ({demand.frequency}) "
            f"reaches {MIN_DEMAND_URGENCY_OR_FREQUENCY}"
        )
    return GateResult(gate="validation", passed=not reasons, reasons=reasons)


def direction_gate(ranking: list[RankedDirection]) -> GateResult:
    """After ranking: is the best direction actually strong, or merely least-bad?"""
    reasons = []
    if not ranking:
        reasons.append("architect produced no directions")
    elif ranking[0].composite < MIN_DIRECTION_COMPOSITE:
        reasons.append(
            f"top composite {ranking[0].composite} < {MIN_DIRECTION_COMPOSITE} — "
            "no direction clears the bar"
        )
    return GateResult(gate="direction", passed=not reasons, reasons=reasons)


def stress_gate(report: StressTestReport, round_index: int) -> GateResult:
    """After each stress test: proceed, refine again, or park.

    passed=True  -> proceed to vision
    passed=False + round_index < MAX_REFINEMENT_ROUNDS -> refine again
    passed=False + rounds exhausted -> park the opportunity (recorded honestly)
    """
    reasons = []
    if report.verdict == "do_not_proceed":
        reasons.append(f"red team verdict: do_not_proceed — {report.reasoning}")
    critical = report.critical_issues
    if critical:
        reasons.extend(
            f"unresolved critical [{i.lens}]: {i.issue}" for i in critical
        )
    return GateResult(
        gate=f"stress-round-{round_index}", passed=not reasons, reasons=reasons
    )
