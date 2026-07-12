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
        "3. the stylesheet (tech: 'CSS stylesheet') — the complete visual "
        "design, DISTINCT to this specific product (see visual identity "
        "note below) — not a reusable generic template.\n"
        "No server components: this app runs from static files alone. Write "
        "data_model as one compact sketch of the exact localStorage keys and "
        "JSON shapes, and api_surface as the DOM element ids / JS function "
        "contracts the three files share — be precise, the engineers build "
        "against these.\n"
        "VISUAL IDENTITY (for the stylesheet component): derive a color "
        "palette, type pairing, and layout mood specifically from THIS "
        "product's name/one-liner/positioning above — never default to a "
        "generic blue-and-white SaaS look. State the concrete direction as "
        "the first sentence of `rationale` (e.g. 'Visual identity: "
        "terminal-green monospace, dark, utilitarian.') so the engineer "
        "builds exactly that, not a template.\n"
        "STRICT OUTPUT RULE: emit every property of the "
        "schema on every object — including 'key_interfaces' and "
        "'depends_on' (use [] when none) — never omit a key.",
        agent="build/architect",
        # Default tier: a live run exhausted all retries on the builder
        # model's 8k TPM ceiling once these instructions grew (reasoning
        # models spend hidden tokens against that budget too) — same story
        # as Engineer/QA, see ADR-0010.
        tier="default",
    )


async def write_scaffold(
    ctx: str,
    plan: BuildPlan,
    architecture: ArchitectureSpec,
    component: ComponentSpec,
    qa_feedback: str = "",
    sibling_files: list[ScaffoldFile] | None = None,
    planned_files: list[str] | None = None,
) -> ScaffoldContent:
    """Success criteria: a complete, working file — every feature wired,
    nothing stubbed; consistent with the files already written (passed in
    as sibling context — this is what makes JS reference real HTML ids);
    directly addresses qa_feedback when present."""
    feedback_block = f"\nQA FEEDBACK TO ADDRESS: {qa_feedback}" if qa_feedback else ""
    planned_block = (
        f"\nTHE APP'S COMPLETE FILE SET (decided, do not invent others): {', '.join(planned_files)}"
        if planned_files
        else ""
    )
    siblings_block = ""
    if sibling_files:
        rendered = "\n".join(f"--- {f.path} (already written) ---\n{f.content[:5000]}" for f in sibling_files)
        siblings_block = (
            f"\n\nFILES ALREADY WRITTEN FOR THIS APP — your file must work with these exactly "
            f"as they are (reference only element ids, classes, and functions that really exist "
            f"in them):\n{rendered}"
        )
    # Raw completion, not structured output: large code files inside a JSON
    # string field are exactly where json_validate_failed lives (a live
    # build lost 4 components in one round to it). Plain text out, code
    # strips any stray markdown fences deterministically.
    text = await venture_agents._completion(
        ctx
        + f"\nBUILD PLAN: {plan.model_dump_json()}"
        + f"\nARCHITECTURE: {architecture.model_dump_json()}"
        + f"\n\nCOMPONENT: {component.name}\n{component.model_dump_json()}"
        + feedback_block
        + planned_block
        + siblings_block
        + f"\n\nYou are the Engineer for the '{component.name}' component of a "
        "self-contained client-side web app (static HTML/CSS/JS, no build "
        "step, no server, no external libraries or CDNs). Write the COMPLETE, "
        "WORKING file for this component ONLY — one file, in this component's "
        "own language. If this is the HTML file: markup only, no inline "
        "<script> or <style> blocks (the CSS/JS live in the app's other "
        "files, which are linked automatically). If this is a JS file: "
        "JavaScript only, no HTML. NO external libraries ever — no Chart.js, "
        "no CDN script tags, no imports; if the product needs a chart or "
        "visualization, draw it yourself with the native canvas 2D API or "
        "inline SVG (a simple bar/line chart is ~30 lines of canvas code). "
        "This ships to real users as-is, so no "
        "TODOs, no placeholder stubs, no Math.random() stand-in logic, no "
        "'for demonstration purposes' shortcuts — implement the real thing, "
        "simply. If this is the stylesheet: follow the ARCHITECTURE's "
        "`rationale` visual-identity direction precisely — a distinct look "
        "for this product, not a generic default. Every P0 feature this "
        "component is responsible for must "
        "actually work when the files are opened in a browser. Stay exactly "
        "consistent with the shared data model (localStorage shapes), the "
        "api_surface (element ids / function contracts), and the sibling "
        "files shown above.\n\n"
        "OUTPUT FORMAT: respond with ONLY the raw file content, starting at "
        "its first character. No preamble, no explanation, no markdown fences.",
        agent="build/engineer",
        # Stays on the default tier deliberately: complete files need a big
        # max_tokens, and the builder model (gpt-oss-120b) sits on an 8k TPM
        # ceiling on this account (ADR-0005) — prompt + a full file would be
        # a permanent 413, not a retryable 429. The default model has 30k.
        tier="default",
        max_tokens=6144,
    )
    return ScaffoldContent(content=_strip_fences(text), key_decisions=[])


def _strip_fences(text: str) -> str:
    """Deterministically unwrap a markdown code fence if the model added one
    despite instructions — never let formatting cost a build round."""
    t = text.strip()
    if t.startswith("```"):
        first_newline = t.find("\n")
        if first_newline != -1 and t.rstrip().endswith("```"):
            t = t[first_newline + 1 :].rstrip()
            t = t[: -3].rstrip("\n") if t.endswith("```") else t
    return t


async def review_scaffold(
    ctx: str,
    plan: BuildPlan,
    architecture: ArchitectureSpec,
    files: list[ScaffoldFile],
    reference_audit: list[str] | None = None,
) -> QAReport:
    """Success criteria: this is a structured document review, not code
    execution — findings reference what's actually written in each file;
    verdict follows from the issues, mirroring stress_test's own rule.
    `reference_audit` is scoring.undefined_dom_ids' output — authoritative
    over anything the model believes about id existence."""
    # Near-full files: a truncated HTML page makes "JS references an id the
    # HTML doesn't define" findings unfalsifiable (observed live round 2).
    # QA runs on the 30k-TPM default tier, which absorbs this comfortably.
    files_block = "\n".join(f"--- {f.component} ({f.path}) ---\n{f.content[:9000]}" for f in files)
    audit_block = (
        "every DOM id referenced by the JS is defined in the HTML"
        if not reference_audit
        else f"ids referenced by the JS but NOT defined in any HTML file: {', '.join(reference_audit)}"
    )
    return await venture_agents._structured(
        QAReport,
        ctx
        + f"\nBUILD PLAN: {plan.model_dump_json()}"
        + f"\nARCHITECTURE: {architecture.model_dump_json()}"
        + f"\n\nPRODUCT FILES — this is the app's COMPLETE file set; every file "
        "named in the architecture appears above (long files truncated for "
        f"review):\n{files_block}"
        + f"\n\nDETERMINISTIC REFERENCE AUDIT (computed by code, authoritative): {audit_block}."
        + "\n\nYou are QA for a shipping product. Review these files against the "
        "build plan and architecture spec as a structured document review — "
        "you are not executing any code. This app deploys to real users as "
        "static files.\n"
        "SEVERITY RUBRIC (apply strictly): critical is reserved for exactly "
        "three things — (1) a P0 feature that visibly does nothing when a "
        "user tries it (a button wired to no handler, a stub/placeholder "
        "implementation), (2) an id listed as missing by the reference audit "
        "above, (3) a dependency on an external library/CDN or a server the "
        "app doesn't have. EVERYTHING ELSE IS AT MOST MAJOR: missing input "
        "validation, unhandled empty/edge cases, an unpopulated optional "
        "field, accessibility gaps, style deviations from the data model / "
        "api_surface. Minor = polish. Verdict must follow from your own "
        "issues: 'blocked' only if a critical issue has no credible fix.\n"
        "HARD RULES: id-existence findings must come ONLY from the reference "
        "audit — never contradict it. Never claim a file is missing when its "
        "block appears above. Never flag truncation. Browser-compatibility "
        "speculation (older browsers, restricted localStorage, disabled JS) "
        "is never an issue at any severity — assume a modern evergreen "
        "browser. In `component`, use the EXACT component name from the "
        "architecture, nothing appended.",
        agent="build/qa",
        # Default tier for the same 8k-TPM reason as the Engineer: QA's
        # prompt now carries three real product files, which alone would
        # crowd the builder model's ceiling into permanent-413 territory.
        tier="default",
    )
