"""Build-squad agents: PM -> Architect -> Engineer (fan-out) -> QA.

Turns one *complete* `OpportunityDossier` (venture pipeline output) into a
scaffold artifact. Same contract as `venture/agents.py`: structured input,
exactly one structured schema out, temperature 0, bounded retry.

Import detail that matters: this module calls the shared LLM seam via
`venture_agents._structured(...)` (module-attribute access), never
`from ..venture.agents import _structured`. The latter binds a local name
at import time that `monkeypatch.setattr(p2pops.venture.agents, "_structured", fake)`
would NOT intercept -- tests would silently fall through to a real Groq call.
Module-attribute access is what makes the one seam actually one seam.
"""

from ..venture import agents as venture_agents
from ..venture.schemas import OpportunityDossier
from .schemas import ArchitectureSpec, BuildPlan, ComponentSpec, QAReport, ScaffoldContent, ScaffoldFile

_CONTEXT_TEMPLATE = """OPPORTUNITY UNDER DEVELOPMENT
Idea: {idea_title}
Product: {product_name}
One-liner: {one_liner}
Value proposition: {value_proposition}
Positioning: {positioning}
Target segment: {target_segment}
Execution strategy (from the venture pipeline): {execution_strategy}
Known risks carried forward: {known_risks}

CHOSEN DIRECTION: {chosen_direction}

SEGMENTS: {segments}
COMPETITIVE LANDSCAPE: {landscape}
"""


def _build_context(dossier: OpportunityDossier) -> str:
    """Mirrors venture/agents.py's `_context()` shape: one shared prompt
    block every build-squad agent prepends its own instructions to."""
    vision = dossier.vision
    return _CONTEXT_TEMPLATE.format(
        idea_title=dossier.idea_title,
        product_name=vision.product_name if vision else "(none)",
        one_liner=vision.one_liner if vision else "(none)",
        value_proposition=vision.value_proposition if vision else "(none)",
        positioning=vision.positioning if vision else "(none)",
        target_segment=vision.target_segment if vision else "(none)",
        execution_strategy=vision.execution_strategy if vision else "(none)",
        known_risks=vision.known_risks if vision else [],
        chosen_direction=dossier.chosen_direction or "(none)",
        segments=dossier.segments.model_dump_json() if dossier.segments else "{}",
        landscape=dossier.landscape.model_dump_json() if dossier.landscape else "{}",
    )


async def write_plan(ctx: str) -> BuildPlan:
    """Success criteria: 3-8 features, P0 first; tech choices grounded in
    the actual product vision, not generic boilerplate; non-goals stated
    so scope can't silently creep during Architect/Engineer."""
    return await venture_agents._structured(
        BuildPlan,
        ctx
        + "\n\nYou are the Product Manager. Turn this validated opportunity into a "
        "bounded v1 build plan: 3-8 features ordered by priority (P0 = must ship "
        "to prove the wedge, P1/P2 = fast follow), each with acceptance criteria "
        "concrete enough for an engineer to build against. Recommend a tech stack "
        "per applicable layer (backend, frontend, database, infra) with a "
        "one-line reason each. List explicit non-goals for v1 — things a team "
        "would be tempted to add that must wait.",
        agent="build/pm",
        tier="builder",
    )


async def design_architecture(ctx: str, plan: BuildPlan) -> ArchitectureSpec:
    """Success criteria: 3-6 components that together cover every P0
    feature; each names a concrete, keyword-matchable technology; the data
    model supports the features without over-normalizing for a scaffold."""
    return await venture_agents._structured(
        ArchitectureSpec,
        ctx
        + f"\nBUILD PLAN: {plan.model_dump_json()}"
        + "\n\nYou are the Architect. Design the v1 system: 3-6 components that "
        "together cover every P0 feature (no more — this is a scaffold, not a "
        "platform). For each component, name a concrete technology plainly (e.g. "
        "'FastAPI service', 'Next.js frontend', 'Postgres schema') so it's "
        "unambiguous what kind of file gets scaffolded for it. Define the data "
        "model the components share, and sketch the API surface between them.",
        agent="build/architect",
        tier="builder",
    )


async def write_scaffold(
    ctx: str,
    plan: BuildPlan,
    architecture: ArchitectureSpec,
    component: ComponentSpec,
    qa_feedback: str = "",
) -> ScaffoldContent:
    """Success criteria: a genuine scaffold (real structure, explicit
    TODOs), not a placeholder comment; consistent with the shared data
    model and api_surface; directly addresses qa_feedback when present."""
    feedback_block = f"\nQA FEEDBACK TO ADDRESS: {qa_feedback}" if qa_feedback else ""
    return await venture_agents._structured(
        ScaffoldContent,
        ctx
        + f"\nBUILD PLAN: {plan.model_dump_json()}"
        + f"\nARCHITECTURE: {architecture.model_dump_json()}"
        + f"\n\nCOMPONENT: {component.name}\n{component.model_dump_json()}"
        + feedback_block
        + f"\n\nYou are the Engineer for the '{component.name}' component. Write its "
        "scaffold file: real structure (imports, key functions/classes/routes/"
        "types as appropriate to its tech), explicit TODO markers for what a "
        "human implements next, and comments only where a design decision needs "
        "explaining. Stay consistent with the shared data model and api_surface. "
        "This is a scaffold, not a finished implementation.",
        agent="build/engineer",
        tier="default",
        max_tokens=3072,
    )


async def review_scaffold(
    ctx: str, plan: BuildPlan, architecture: ArchitectureSpec, files: list[ScaffoldFile]
) -> QAReport:
    """Success criteria: this is a structured document review, not code
    execution — findings reference what's actually written in each file;
    verdict follows from the issues, mirroring stress_test's own rule."""
    files_block = "\n".join(f"--- {f.component} ({f.path}) ---\n{f.content[:2000]}" for f in files)
    return await venture_agents._structured(
        QAReport,
        ctx
        + f"\nBUILD PLAN: {plan.model_dump_json()}"
        + f"\nARCHITECTURE: {architecture.model_dump_json()}"
        + f"\n\nSCAFFOLD FILES:\n{files_block}"
        + "\n\nYou are QA. Review these scaffold files against the build plan and "
        "architecture spec as a structured document review — you are not "
        "executing any code. Flag: missing P0 coverage, inconsistency with the "
        "shared data model or api_surface, and any component whose scaffold "
        "doesn't match its stated responsibility. Severity: critical = blocks "
        "the scaffold from being a usable starting point; major = should fix "
        "before building on it; minor = polish. Verdict must follow from your "
        "own issues: 'blocked' if any critical issue has no credible fix.",
        agent="build/qa",
        tier="builder",
    )
