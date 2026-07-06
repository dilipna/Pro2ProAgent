"""Structured artifacts produced by the venture pipeline.

Every agent's output is one of these models — no free-text handoffs. Numeric
fields deliberately avoid JSON-schema min/max (Anthropic's structured-output
validator rejects them); ranges are enforced by clamping validators instead,
so a slightly-out-of-range model output degrades gracefully rather than
failing the run.

All 0-100 scores share the same semantics: 0 = catastrophically weak,
50 = genuinely uncertain, 100 = overwhelming evidence. Confidence is 0-1.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


def _clamp100(value: int) -> int:
    return max(0, min(100, value))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class Score100Mixin:
    """Shared clamping for 0-100 integer score fields (see module docstring)."""


# --- Evidence -----------------------------------------------------------------


class EvidenceItem(BaseModel):
    """One piece of external evidence gathered deterministically (no LLM)."""

    source: str  # "hackernews" | "article"
    title: str
    url: str
    detail: str = ""  # points/comments for HN, excerpt for articles


class EvidenceBundle(BaseModel):
    query: str
    items: list[EvidenceItem] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.items


# --- Parallel analysis artifacts ------------------------------------------------


class ProblemValidation(BaseModel):
    """Validator output: is this problem real, recurring, and important?"""

    is_real: bool = Field(description="True only if the evidence shows real people hitting this problem")
    recurrence: int = Field(description="0-100: how often the problem recurs for those affected")
    importance: int = Field(description="0-100: how costly/painful the problem is when it occurs")
    evidence_summary: str = Field(description="2-4 sentences citing the specific evidence relied on")
    counter_signals: list[str] = Field(
        default_factory=list, description="Evidence that the problem may be overstated or shrinking"
    )
    confidence: float = Field(description="0-1: confidence in this validation given evidence quality")

    _c1 = field_validator("recurrence", "importance")(_clamp100)
    _c2 = field_validator("confidence")(_clamp01)


class UserSegment(BaseModel):
    name: str = Field(description="Short segment label, e.g. 'platform teams at 50-500 eng companies'")
    motivation: str = Field(description="What outcome this segment is actually buying")
    current_workaround: str = Field(description="How they cope today")
    reachability: int = Field(description="0-100: how findable/addressable this segment is")

    _c1 = field_validator("reachability")(_clamp100)


class SegmentAnalysis(BaseModel):
    segments: list[UserSegment] = Field(description="2-4 distinct segments, most affected first")
    primary_segment: str = Field(description="Name of the segment to build for first, and why in one clause")
    confidence: float = Field(description="0-1")

    _c1 = field_validator("confidence")(_clamp01)


class DemandAssessment(BaseModel):
    urgency: int = Field(description="0-100: do affected users need relief now, or is it a nice-to-have")
    frequency: int = Field(description="0-100: how often the pain is encountered in normal work")
    willingness_to_pay: int = Field(description="0-100: strength of budget/pricing signals for a fix")
    demand_signals: list[str] = Field(description="Concrete observed signals, each tied to evidence")
    market_size_reasoning: str = Field(description="Order-of-magnitude reasoning about who pays, not fake TAM math")
    confidence: float = Field(description="0-1")

    _c1 = field_validator("urgency", "frequency", "willingness_to_pay")(_clamp100)
    _c2 = field_validator("confidence")(_clamp01)


class ExistingSolution(BaseModel):
    name: str
    approach: str = Field(description="How it attacks the problem")
    shortcoming: str = Field(description="Where it concretely falls short, per evidence")


class CompetitorLandscape(BaseModel):
    solutions: list[ExistingSolution] = Field(description="Known tools/products/workarounds in this space")
    unserved_gap: str = Field(description="The sharpest gap none of them cover — the wedge")
    saturation: int = Field(description="0-100: how crowded the space is (100 = saturated)")
    confidence: float = Field(description="0-1")

    _c1 = field_validator("saturation")(_clamp100)
    _c2 = field_validator("confidence")(_clamp01)


# --- Solution generation & ranking ----------------------------------------------


class SolutionDirection(BaseModel):
    """One candidate approach. The architect must produce several of these."""

    name: str = Field(description="Memorable working name for the direction")
    approach: str = Field(description="What gets built and how it attacks the unserved gap")
    principle: str = Field(description="Which venture principle from the provided library this applies, and why it transfers")
    wedge: str = Field(description="The narrow first use-case that wins before any expansion")
    # Sub-scores consumed by the deterministic ranking model:
    problem_fit: int = Field(description="0-100: how directly this relieves the validated pain")
    feasibility: int = Field(description="0-100: buildable by a small team in months, not years")
    differentiation: int = Field(description="0-100: distance from existing solutions' approaches")
    monetization_path: int = Field(description="0-100: clarity of who pays and why")
    key_risk: str = Field(description="The single assumption most likely to kill this direction")

    _c1 = field_validator("problem_fit", "feasibility", "differentiation", "monetization_path")(_clamp100)


class DirectionSlate(BaseModel):
    directions: list[SolutionDirection] = Field(description="4-6 meaningfully different directions")
    rejected_framings: list[str] = Field(
        default_factory=list,
        description="Framings considered and discarded, with the reason — guards against first-idea bias",
    )


class RankedDirection(BaseModel):
    """Deterministic scoring output — computed in code, not by an LLM."""

    name: str
    composite: float
    breakdown: dict[str, float]


# --- Stress testing & refinement -------------------------------------------------


class StressIssue(BaseModel):
    lens: str  # technical | business | financial | operational | user
    severity: str  # critical | major | minor
    issue: str = Field(description="The specific failure scenario, stated concretely")
    mitigation: str = Field(description="The best available mitigation, or 'none known'")


class StressTestReport(BaseModel):
    issues: list[StressIssue] = Field(default_factory=list)
    verdict: str = Field(description="'proceed' | 'proceed_with_mitigations' | 'do_not_proceed'")
    reasoning: str = Field(description="Why this verdict, referencing the worst issues")

    @property
    def critical_issues(self) -> list[StressIssue]:
        return [i for i in self.issues if i.severity == "critical"]


class RefinedDirection(BaseModel):
    """Refiner output: the direction revised to answer stress-test findings."""

    revised_approach: str = Field(description="The updated approach, changed where issues demanded it")
    revised_wedge: str
    changes_made: list[str] = Field(description="Each change, mapped to the issue it answers")
    issues_unresolved: list[str] = Field(
        default_factory=list, description="Issues that cannot be designed away — carried as known risks"
    )


# --- Final product vision ---------------------------------------------------------


class ProductVision(BaseModel):
    product_name: str
    one_liner: str = Field(description="A sentence a stranger understands in five seconds")
    value_proposition: str = Field(description="The outcome delivered, for whom, versus their real alternative")
    positioning: str = Field(description="Category and against-whom framing")
    differentiation: list[str] = Field(description="2-4 durable edges, each tied to the landscape analysis")
    target_segment: str
    execution_strategy: str = Field(description="First 90 days: wedge, channel, and the first proof of value")
    success_metrics: list[str] = Field(description="3-5 measurable signals that the product is working")
    known_risks: list[str] = Field(default_factory=list)


# --- The dossier -------------------------------------------------------------------


class GateResult(BaseModel):
    gate: str
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class OpportunityDossier(BaseModel):
    """The complete, traceable record of one idea's journey through the
    venture pipeline. Everything the strategist concluded, and every gate
    decision along the way, in one reproducible artifact."""

    idea_id: str
    idea_title: str
    status: str  # validated | rejected | parked | complete
    evidence: EvidenceBundle
    validation: ProblemValidation | None = None
    segments: SegmentAnalysis | None = None
    demand: DemandAssessment | None = None
    landscape: CompetitorLandscape | None = None
    slate: DirectionSlate | None = None
    ranking: list[RankedDirection] = Field(default_factory=list)
    chosen_direction: str | None = None
    stress_reports: list[StressTestReport] = Field(default_factory=list)
    refinements: list[RefinedDirection] = Field(default_factory=list)
    vision: ProductVision | None = None
    gates: list[GateResult] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
