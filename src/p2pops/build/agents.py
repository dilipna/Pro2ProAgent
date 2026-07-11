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
    """Success criteria: 3-8 features, P0 first; every feature implementable
    as a self-contained client-side web app (the v1 delivery constraint);
    non-goals stated so scope can't silently creep during Architect/Engineer."""
    return await venture_agents._structured(
        BuildPlan,
        ctx
        + "\n\nYou are the Product Manager. Turn this validated opportunity into a "
        "bounded v1 build plan: 3-8 features ordered by priority (P0 = must ship "
        "to prove the wedge, P1/P2 = fast follow; AT MOST 3 features may be P0 — "
        "a v1 that ships three working features beats one that stubs six), each "
        "with acceptance criteria concrete enough for an engineer to build against.\n\n"
        "HARD DELIVERY CONSTRAINT for v1: the product ships as a self-contained "
        "client-side web application — static HTML/CSS/JavaScript that runs "
        "entirely in the browser, persisting data with localStorage, with no "
        "server, no build step, and no external API dependency. Choose P0 "
        "features that deliver genuine working value inside that constraint "
        "(interactive tools, calculators, analyzers, trackers, checklists with "
        "real logic — not a marketing page). Anything that truly needs a "
        "backend goes in non_goals for v1. Tech stack choices must reflect "
        "this constraint (frontend: vanilla HTML/CSS/JS; storage: localStorage).",
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
        + "\n\nYou are the Architect. Design the v1 system: exactly 3 components "
        "that together cover every P0 feature, one per browser file of a "
        "self-contained client-side web app:\n"
        "1. the HTML page (tech: 'HTML page') — full semantic markup, every "
        "screen/section/control the features need, ids/classes the JS hooks into;\n"
        "2. the application logic (tech: 'JavaScript browser logic with "
        "localStorage') — all interactivity, state, and persistence;\n"
        "3. the stylesheet (tech: 'CSS stylesheet') — the complete visual design.\n"
        "No server components: this app runs from static files alone. Define the "
        "shared data model (the exact object shapes stored in localStorage) and "
        "the api_surface as the DOM element ids / JS function contracts the "
        "three files share — be precise, the engineers build against these.",
        agent="build/architect",
        tier="builder",
    )


async def write_scaffold(
    ctx: str,
    plan: BuildPlan,
    architecture: ArchitectureSpec,
    component: ComponentSpec,
    qa_feedback: str = "",
    sibling_files: list[ScaffoldFile] | None = None,
) -> ScaffoldContent:
    """Success criteria: a complete, working file — every feature wired,
    nothing stubbed; consistent with the files already written (passed in
    as sibling context — this is what makes JS reference real HTML ids);
    directly addresses qa_feedback when present."""
    feedback_block = f"\nQA FEEDBACK TO ADDRESS: {qa_feedback}" if qa_feedback else ""
    siblings_block = ""
    if sibling_files:
        rendered = "\n".join(f"--- {f.path} (already written) ---\n{f.content[:5000]}" for f in sibling_files)
        siblings_block = (
            f"\n\nFILES ALREADY WRITTEN FOR THIS APP — your file must work with these exactly "
            f"as they are (reference only element ids, classes, and functions that really exist "
            f"in them):\n{rendered}"
        )
    return await venture_agents._structured(
        ScaffoldContent,
        ctx
        + f"\nBUILD PLAN: {plan.model_dump_json()}"
        + f"\nARCHITECTURE: {architecture.model_dump_json()}"
        + f"\n\nCOMPONENT: {component.name}\n{component.model_dump_json()}"
        + feedback_block
        + siblings_block
        + f"\n\nYou are the Engineer for the '{component.name}' component of a "
        "self-contained client-side web app (static HTML/CSS/JS, no build "
        "step, no server, no external libraries or CDNs). Write the COMPLETE, "
        "WORKING file for this component — this ships to real users as-is, so "
        "no TODOs, no placeholder stubs, no unimplemented buttons. Every P0 "
        "feature this component is responsible for must actually work when "
        "the files are opened in a browser. Stay exactly consistent with the "
        "shared data model (localStorage shapes) and api_surface (element ids "
        "/ function contracts) so the three files work together. Content only "
        "— no markdown fences around the code.",
        agent="build/engineer",
        # Stays on the default tier deliberately: complete files need a big
        # max_tokens, and the builder model (gpt-oss-120b) sits on an 8k TPM
        # ceiling on this account (ADR-0005) — prompt + a full file would be
        # a permanent 413, not a retryable 429. The default model has 30k.
        tier="default",
        max_tokens=6144,
    )


async def review_scaffold(
    ctx: str, plan: BuildPlan, architecture: ArchitectureSpec, files: list[ScaffoldFile]
) -> QAReport:
    """Success criteria: this is a structured document review, not code
    execution — findings reference what's actually written in each file;
    verdict follows from the issues, mirroring stress_test's own rule."""
    # Near-full files: a truncated HTML page makes "JS references an id the
    # HTML doesn't define" findings unfalsifiable (observed live round 2).
    # QA runs on the 30k-TPM default tier, which absorbs this comfortably.
    files_block = "\n".join(f"--- {f.component} ({f.path}) ---\n{f.content[:9000]}" for f in files)
    return await venture_agents._structured(
        QAReport,
        ctx
        + f"\nBUILD PLAN: {plan.model_dump_json()}"
        + f"\nARCHITECTURE: {architecture.model_dump_json()}"
        + f"\n\nPRODUCT FILES (each truncated for review):\n{files_block}"
        + "\n\nYou are QA for a shipping product. Review these files against the "
        "build plan and architecture spec as a structured document review — "
        "you are not executing any code. This app deploys to real users as "
        "static files, so flag as critical anything that would make it not "
        "work in a browser: unimplemented or stubbed P0 features, JS that "
        "references element ids the HTML verifiably does not define, broken "
        "references between the three files, use of external libraries/CDNs "
        "or a server the app doesn't have. In `component`, use the EXACT "
        "component name from the architecture, nothing appended. Major = "
        "works but deviates from the data model / api_surface; minor = "
        "polish. Verdict must follow from your own issues: 'blocked' if any "
        "critical issue has no credible fix. Do not flag file truncation "
        "itself, and do not report an id as undefined unless you can see the "
        "full HTML and it is genuinely absent.",
        agent="build/qa",
        # Default tier for the same 8k-TPM reason as the Engineer: QA's
        # prompt now carries three real product files, which alone would
        # crowd the builder model's ceiling into permanent-413 territory.
        tier="default",
    )
