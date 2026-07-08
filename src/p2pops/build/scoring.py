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
    (("javascript", "js", "logic", "browser", "localstorage"), "app.js", "javascript"),
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
