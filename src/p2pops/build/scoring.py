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
_LANGUAGE_KEYWORDS: list[tuple[tuple[str, ...], str, str]] = [
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
