"""Structured artifacts produced by the build-squad subgraph.

Same contract as `venture/schemas.py`: every agent output is one of these
models, never free text. One addition here that venture doesn't need:
`ScaffoldContent` (what the LLM is allowed to write) and `ScaffoldFile`
(what actually gets persisted) are deliberately separate models. The LLM
is never given a `path` or `language` field to fill in -- those are
computed by `build/scoring.py`'s `scaffold_target()` from the component's
`tech` string, so a hallucinated or unsafe path can never reach storage.
This is the same "code decides, LLM produces" split as venture's
`SolutionDirection` (LLM-authored) vs. `RankedDirection` (code-computed).
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..venture.schemas import GateResult

__all__ = [
    "GateResult",
    "BuildFeature",
    "StackChoice",
    "BuildPlan",
    "ComponentSpec",
    "ArchitectureSpec",
    "ProductDesign",
    "ScaffoldContent",
    "ScaffoldFile",
    "QAIssue",
    "QAReport",
    "BuildDossier",
]


# --- PM ------------------------------------------------------------------------


class BuildFeature(BaseModel):
    name: str
    description: str
    priority: str = Field(description="'P0' (must ship) | 'P1' | 'P2'")
    acceptance_criteria: list[str] = Field(default_factory=list)


class StackChoice(BaseModel):
    layer: str = Field(description="e.g. 'backend' | 'frontend' | 'database' | 'infra'")
    choice: str
    rationale: str = Field(description="One line: why this, for this specific product")


class BuildPlan(BaseModel):
    """PM output: the bounded v1 scope, not a wishlist."""

    features: list[BuildFeature] = Field(description="3-8 prioritized features, P0 first")
    tech_stack: list[StackChoice]
    non_goals: list[str] = Field(default_factory=list, description="Explicitly descoped for v1, and why")


# --- Architect -------------------------------------------------------------------
# NOTE: the data model is deliberately a flat string, not nested
# entity/field objects. Groq's strict structured-output mode requires every
# schema property present on every object, and small models were observed
# repeatedly omitting deep-nested keys ('relationships', 'note') — 4/4
# failed generations in one live build. Every removed nesting level removes
# an omission surface; the engineers consume the data model as prose anyway.


class ComponentSpec(BaseModel):
    """One buildable unit. `name` is the canonical key Engineer/QA/revise
    match against -- must be stable and unique within one ArchitectureSpec."""

    name: str
    responsibility: str
    tech: str = Field(
        description="Name a concrete technology plainly (e.g. 'FastAPI service', "
        "'Next.js frontend', 'Postgres schema') -- this string is keyword-matched "
        "by code to choose the scaffold file's language, not free-form prose."
    )
    key_interfaces: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list, description="Other ComponentSpec.name values")


class ProductDesign(BaseModel):
    """A shared product-specific contract, authored in the existing architect call.

    This describes intended UI behavior; it is not evidence of a rendered result.
    Flat, bounded fields keep the structured output practical for smaller models.
    """

    primary_workflow: str = Field(min_length=20, max_length=600, description="User, task, steps and useful result; respect the approved scope")
    layout: str = Field(min_length=20, max_length=600, description="Named screen regions and their hierarchy; justify a workspace, editor, timeline or other task-shaped layout")
    visual_direction: str = Field(min_length=20, max_length=500, description="Product-specific character, concrete colors with hex values, type stacks, spacing and density; no generic SaaS template")
    signature_detail: str = Field(min_length=10, max_length=400, description="One useful, distinctive interaction or visualization already inside approved scope; no decorative metrics")
    states: list[str] = Field(min_length=3, max_length=6, description="Concrete initial, empty, invalid and completed states; label sample data and offer a clear/reset path")
    responsive_rules: str = Field(min_length=20, max_length=500, description="How task regions reflow at 390px and 1440px, keyboard focus, readable contrast and touch targets")


class ArchitectureSpec(BaseModel):
    """Architect output."""

    components: list[ComponentSpec] = Field(description="Components covering the BuildPlan's P0 features")
    data_model: str = Field(
        description="The exact object shapes the app stores (e.g. localStorage keys and their "
        "JSON shapes), written as a compact sketch the engineers copy from"
    )
    api_surface: list[str] = Field(
        default_factory=list, description="Element ids / function contracts, one per line"
    )
    rationale: str = Field(description="One line: why this shape fits the plan")
    product_design: ProductDesign | None = Field(
        default=None,
        description="Always provide for new browser products. Shared UX and visual contract consumed by all engineers and QA. Null only for legacy/non-browser records.",
    )


# --- Engineer --------------------------------------------------------------------


class ScaffoldContent(BaseModel):
    """LLM-facing ONLY. No path/language field -- ever. See module docstring."""

    content: str = Field(description="The complete working file; no TODOs or placeholder behavior")
    key_decisions: list[str] = Field(default_factory=list)


class ScaffoldFile(BaseModel):
    """Code-composed after the call; this is what gets persisted."""

    component: str
    path: str
    language: str
    content: str
    key_decisions: list[str] = Field(default_factory=list)


# --- QA ------------------------------------------------------------------------


class QAIssue(BaseModel):
    component: str = Field(description="Must name a real ComponentSpec.name")
    severity: Literal["critical", "major", "minor"]
    issue: str
    fix: str


class QAReport(BaseModel):
    """QA output. This is a structured document review of the scaffold
    against the architecture spec -- explicitly NOT sandboxed code
    execution or running real tests. Naming/docs should never imply
    otherwise."""

    issues: list[QAIssue] = Field(default_factory=list)
    verdict: Literal["approved", "needs_revision", "blocked"]
    reasoning: str

    @property
    def critical_issues(self) -> list[QAIssue]:
        return [i for i in self.issues if i.severity == "critical"]


# --- The build dossier -----------------------------------------------------------


class BuildDossier(BaseModel):
    """The complete, traceable record of one opportunity's journey through
    the build-squad subgraph."""

    opportunity_id: str
    idea_title: str
    approved_snapshot: dict | None = None
    product_name: str | None = None
    status: str  # scaffolding | complete | needs_revision | failed
    plan: BuildPlan | None = None
    architecture: ArchitectureSpec | None = None
    scaffold_files: list[ScaffoldFile] = Field(
        default_factory=list, description="CURRENT state only -- replaced wholesale per revised component"
    )
    qa_reports: list[QAReport] = Field(
        default_factory=list, description="Append-only across rounds -- the argument, not just the conclusion"
    )
    gates: list[GateResult] = Field(default_factory=list)
    deploy_url: str | None = Field(
        default=None, description="Public URL of the published product; None = built but not published"
    )
    verification_scope: str | None = Field(
        default=None, description="Code-authored description of which checks actually ran; null for historical records"
    )
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
