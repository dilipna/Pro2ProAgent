"""Code-decided logic for the build-squad subgraph.

Same anti-"vibes" line as `venture/scoring.py`: the LLM agents propose (a
plan, an architecture, scaffold content); this module is where a pass/fail
verdict and a file's path/language are actually decided, in plain Python.
"""

from .schemas import ComponentSpec, GateResult, QAReport

MAX_QA_ROUNDS = 2
# Same convention as venture's MAX_REFINEMENT_ROUNDS: this is the total
# number of QA rounds allowed (round_index reaches this value before the
# loop gives up), so MAX_QA_ROUNDS=2 means exactly one revision round --
# round 1 fails -> revise -> round 2 is final. Unlike venture's
# stress/refine loop (1 LLM call per round), Engineer fans out N calls
# per round (N = components, typically 3-6). Worst case at N=6:
# PM(1) + Architect(1) + Engineer(6) + QA(1) + revise-Engineer(<=6) +
# QA(1) ~= 16 calls -- already comparable to venture's own worst case
# (~10). Raising this to 3 would push worst case to roughly 22 -- do not
# raise without re-deriving that cost math.


def qa_gate(report: QAReport, round_index: int) -> GateResult:
    """Mirrors stress_gate's two independent failure conditions: an explicit
    'blocked' verdict, OR any unresolved critical issue -- either one fails
    the gate regardless of the other."""
    reasons = []
    if report.verdict == "blocked":
        reasons.append(f"QA verdict: blocked — {report.reasoning}")
    reasons.extend(f"unresolved critical [{i.component}]: {i.issue}" for i in report.critical_issues)
    return GateResult(gate=f"qa-round-{round_index}", passed=not reasons, reasons=reasons)


# Ordered so the first matching keyword wins; checked against `tech.lower()`.
# The browser-file rows come first: since the MVP pivot the Architect is
# instructed to design a self-contained client-side web app, so HTML/JS/CSS
# are the expected component techs; the server-side rows remain as fallbacks
# for any component the Architect frames that way (those files ship in the
# dossier but are not browser-deployable — publish.py filters them).
_LANGUAGE_KEYWORDS: list[tuple[tuple[str, ...], str, str]] = [
    (("html", "page", "markup", "ui"), "index.html", "html"),
    (("css", "style", "design system"), "styles.css", "css"),
    # No bare "js" keyword: it substring-matches "Next.js" and misroutes
    # server-rendered frontends to app.js (caught by the offline suite).
    (("javascript", "logic", "browser", "localstorage"), "app.js", "javascript"),
    (("fastapi", "flask", "django", "python"), "main.py", "python"),
    (("next.js", "nextjs", "react", "typescript", "node"), "index.tsx", "typescript"),
    (("postgres", "sql", "schema", "database"), "schema.sql", "sql"),
]


def scaffold_target(component: ComponentSpec) -> tuple[str, str]:
    """Deterministic (filename, language) from `component.tech` -- the LLM
    never chooses a path or language, only the file's `content`. Falls
    back to a README when no tech keyword matches, so every component
    still gets a real, inspectable scaffold file."""
    tech = component.tech.lower()
    for keywords, filename, language in _LANGUAGE_KEYWORDS:
        if any(k in tech for k in keywords):
            return filename, language
    return "README.md", "markdown"


def _slug(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "component"


def link_assets(files: list) -> list:
    """Deterministically guarantee every built CSS/JS file is referenced
    from every HTML file (<link> before </head>, <script src defer> before
    </body>). Small models systematically forget or misorder these tags —
    observed live as a QA-blocking critical two builds running — and tag
    insertion is exactly the kind of decision code should own, not an LLM."""
    css = [f.path for f in files if f.path.lower().endswith(".css")]
    js = [f.path for f in files if f.path.lower().endswith(".js")]
    for f in files:
        if not f.path.lower().endswith(".html"):
            continue
        content = f.content
        for path in css:
            if path not in content:
                tag = f'<link rel="stylesheet" href="{path}">'
                content = (
                    content.replace("</head>", f"  {tag}\n</head>", 1)
                    if "</head>" in content
                    else tag + "\n" + content
                )
        for path in js:
            if path not in content:
                tag = f'<script src="{path}" defer></script>'
                content = (
                    content.replace("</body>", f"  {tag}\n</body>", 1)
                    if "</body>" in content
                    else content + "\n" + tag
                )
        f.content = content
    return files


def consolidate_components(components: list[ComponentSpec]) -> list[ComponentSpec]:
    """Deterministically collapse an over-decomposed architecture toward the
    three-browser-file shape: all components sharing the html, css, or
    javascript target language merge into one component per language (first
    member's name; responsibilities and interfaces unioned). The Architect
    is instructed to produce exactly 3 components but observed live emitting
    6 — and each extra JS component is another engineer call, more sibling
    context, and another cross-file drift surface. Structure is a code
    decision. Components in other languages pass through untouched."""
    merge_languages = ("html", "css", "javascript")
    groups: dict[str, list[ComponentSpec]] = {}
    ordered_keys: list[str] = []
    for index, component in enumerate(components):
        _, language = scaffold_target(component)
        key = language if language in merge_languages else f"passthrough-{index}"
        if key not in groups:
            groups[key] = []
            ordered_keys.append(key)
        groups[key].append(component)

    consolidated: list[ComponentSpec] = []
    for key in ordered_keys:
        members = groups[key]
        if len(members) == 1:
            consolidated.append(members[0])
            continue
        first = members[0]
        interfaces: list[str] = []
        for m in members:
            interfaces.extend(i for i in m.key_interfaces if i not in interfaces)
        consolidated.append(
            ComponentSpec(
                name=first.name,
                responsibility="; ".join(m.responsibility for m in members),
                tech=first.tech,
                key_interfaces=interfaces[:16],
                depends_on=[],
            )
        )
    return consolidated


def undefined_dom_ids(files: list) -> list[str]:
    """Deterministic cross-file reference audit: every DOM id the JS
    references (getElementById / #-selectors) that no HTML file defines.
    Exists because the LLM QA reviewer was observed flagging id-existence
    issues that were verifiably false (and missing real ones behind
    truncation) — id existence is a grep, not a judgment call. The QA
    prompt receives this audit as authoritative."""
    import re

    html = "\n".join(f.content for f in files if f.path.lower().endswith(".html"))
    defined = set(re.findall(r"""id\s*=\s*["']([\w-]+)["']""", html))
    referenced: set[str] = set()
    for f in files:
        if not f.path.lower().endswith(".js"):
            continue
        referenced |= set(re.findall(r"""getElementById\(\s*["']([\w-]+)["']""", f.content))
        referenced |= set(re.findall(r"""querySelector(?:All)?\(\s*["']#([\w-]+)["']""", f.content))
    return sorted(referenced - defined)


def ensure_browser_components(components: list[ComponentSpec]) -> list[ComponentSpec]:
    """Guarantee the app has an HTML page and a JS logic component —
    injected deterministically when the Architect's slate lacks them
    (observed live: a 'consolidated' architecture with no HTML component at
    all, which QA then correctly blocked as an app with no page). The
    synthetic spec is generic on purpose; the Engineer writes it against
    the full plan/architecture context like any other component.

    Only applies to browser-shaped slates (at least one html/css/js
    component): a slate with no browser component at all is a different
    architecture, not a missing file — injecting a bare page into it
    wouldn't make it shippable."""
    languages = {scaffold_target(c)[1] for c in components}
    if not languages & {"html", "css", "javascript"}:
        return list(components)
    result = list(components)
    if "html" not in languages:
        result.insert(
            0,
            ComponentSpec(
                name="HTML Page",
                responsibility=(
                    "The complete page markup for every P0 feature — every section, control, "
                    "and element id the application logic references must be defined here"
                ),
                tech="HTML page",
            ),
        )
    if "javascript" not in languages:
        result.append(
            ComponentSpec(
                name="Application Logic",
                responsibility="All interactivity, state, and localStorage persistence for the P0 features",
                tech="JavaScript browser logic with localStorage",
            ),
        )
    return result


def scaffold_targets(components: list[ComponentSpec]) -> dict[str, tuple[str, str]]:
    """Unique (path, language) per component, decided once per architecture
    so paths stay stable across QA revision rounds. Collisions (two 'JS
    logic' components, say) get a deterministic component-slug prefix; the
    first claimant keeps the canonical name, so index.html stays the app's
    entry page."""
    taken: set[str] = set()
    targets: dict[str, tuple[str, str]] = {}
    for component in components:
        path, language = scaffold_target(component)
        if path in taken:
            path = f"{_slug(component.name)}-{path}"
        taken.add(path)
        targets[component.name] = (path, language)
    return targets
