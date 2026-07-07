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

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ..venture.schemas import GateResult

__all__ = [
    "GateResult",
    "BuildFeature",
    "StackChoice",
    "BuildPlan",
    "DataField",
    "DataEntity",
    "DataModel",
    "ComponentSpec",
    "ArchitectureSpec",
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


class DataField(BaseModel):
    name: str
    type: str
    note: str = ""


class DataEntity(BaseModel):
    name: str
    fields: list[DataField] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list, description="Free-text refs to other entities")


class DataModel(BaseModel):
    entities: list[DataEntity] = Field(default_factory=list)
    notes: str = ""


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


class ArchitectureSpec(BaseModel):
    """Architect output."""

    components: list[ComponentSpec] = Field(description="3-6 components covering the BuildPlan's P0 features")
    data_model: DataModel
    api_surface: list[str] = Field(default_factory=list, description="Endpoint/interface sketches, one line each")
    rationale: str = Field(description="One line: why this shape fits the plan")


# --- Engineer --------------------------------------------------------------------


class ScaffoldContent(BaseModel):
    """LLM-facing ONLY. No path/language field -- ever. See module docstring."""

    content: str = Field(description="The full scaffold file contents, with explicit TODOs where stubbed")
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
    severity: str = Field(description="'critical' | 'major' | 'minor'")
    issue: str
    fix: str


class QAReport(BaseModel):
    """QA output. This is a structured document review of the scaffold
    against the architecture spec -- explicitly NOT sandboxed code
    execution or running real tests. Naming/docs should never imply
    otherwise."""

    issues: list[QAIssue] = Field(default_factory=list)
    verdict: str = Field(description="'approved' | 'needs_revision' | 'blocked'")
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
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
