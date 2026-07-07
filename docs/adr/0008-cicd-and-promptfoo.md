# ADR-0008: CI/CD pipeline and Promptfoo prompt regression testing

**Date:** 2026-07-07 · **Status:** Accepted

## Context

Two related gaps remained after Phase 3: no CI at all (`PROJECT_BRAIN.md`
§8 — "No `.github/workflows/` directory exists"), and Promptfoo unintegrated
— the last of the three originally-named LLMOps tools with zero
implementation (LangSmith/Logfire and the homegrown Braintrust-equivalent
eval were both already live as of Phase 3). Closing both together makes
sense: the natural first Promptfoo integration point *is* a CI job.

## Decision

### `ci.yml`: free, on every push — never calls a paid LLM

Three parallel jobs (backend lint+test, web lint+build, Docker build
validation) plus a fourth that validates `promptfooconfig.yaml`'s *schema*
only (`promptfoo validate config`, confirmed via reading promptfoo's own CLI
help to distinguish it from `validate target`, which actually invokes
providers). This job set answers "did this push break anything
deterministic" without ever touching a rate-limited or metered API — the
same cost-consciousness that shaped `resilience.py` and the Groq model
choice (ADR-0005) applies to CI design too.

### `promptfoo.yml`: separate workflow, manual + weekly, real LLM calls, gated

Prompt regression testing is the one CI concern that *must* call a real
provider — the entire point is catching behavioral drift in what the model
actually does. Running it on every push would mean every commit (including
docs-only changes) burns Groq tokens and can fail CI on the same kind of
transient rate-limit event ADR-0005 spent five bug-fixes making the
*application* resilient to. So this workflow is `workflow_dispatch` +
weekly `schedule`, and its first step checks `secrets.GROQ_API_KEY` and
skips with a `::notice::` (not a failure) if unset — identical in spirit to
`evals/analyst_eval.py` shipping dependency-free when no Braintrust key
exists: **degrade honestly, never fail loudly for a missing optional
integration, never fake success either.**

### The Promptfoo provider calls the real agent functions, not a prompt copy

`src/p2pops/evals/promptfoo_provider.py` is a promptfoo `exec:` provider
(protocol verified by reading `ScriptCompletionProvider.callApi` in
promptfoo's own source rather than assuming: argv[1]=rendered prompt (unused
here), argv[2]=options JSON, argv[3]=context JSON containing `vars`; exactly
one line of stdout becomes the provider's `output`). `vars.agent` dispatches
to `p2pops.agents.analyst.analyze_idea` or `p2pops.venture.agents
.validate_problem` — the actual production functions, imported directly, not
duplicated prompt strings. This is the same principle the venture/build test
suites already follow with the `_structured` seam: **a regression test that
exercises a copy of the behavior only ever catches drift between the copy
and the original, never a real regression in the original.**

Each subprocess invocation sets `DATA_DIR` to a fresh `tempfile.mkdtemp()`
before any `p2pops` import, so the Analyst's ChromaDB dedupe store never
leaks state between scenarios or across runs — a real hermeticity
requirement discovered while designing this, not a hypothetical one (two
semantically-similar test titles run in the same store could otherwise
"deduplicate" each other and silently short-circuit the scoring call being
tested).

### Five scenarios, generous thresholds, honest about being regression
signals rather than correctness proofs

- Analyst: guardrail blocks an obvious spam/off-topic submission (assert
  `status == "rejected"` with guardrail-attributed reasoning — near-zero
  flake, since this is a discrete code branch, not a score threshold).
- Analyst: a specific, painful, buildable problem clears guardrails and
  scores above a generous floor (25, against a shortlist threshold of 50) —
  wide enough to absorb normal LLM-to-LLM variance, tight enough to catch a
  broken or inverted scorer.
- Analyst: a vague non-problem does not score as a standout. **Found live**
  during verification: the crafted scenario ("just a general thought") was
  vague enough that the *guardrail itself* correctly blocked it before
  scoring ever ran, per its own documented "too vague to act on" criterion —
  a genuinely correct outcome the first version of this assertion didn't
  anticipate. Fixed to accept either valid outcome (guardrail-blocked with a
  null score, or scored low) rather than loosening the guardrail's own
  behavior to fit a narrow test expectation.
- Venture Validator: strong fabricated evidence produces a well-formed,
  grounded verdict (schema-shape assertions plus a non-trivial
  `evidence_summary`).
- Venture Validator: zero evidence keeps `confidence` under a generous
  ceiling (0.75) — a direct regression check on the prompt's own explicit
  instruction ("lower your confidence accordingly" when evidence is thin),
  worded loosely enough to not flag ordinary variance.

All five were run live against the funded Groq key during this session (not
just schema-validated) — 4/5 passed on the first real run, the one failure
was the test-design gap above, and 5/5 passed after the fix. This mirrors
the project's standing practice of live-verifying rather than trusting a
green offline suite alone (ADR-0005, ADR-0006, Phase 3's build-squad
verification).

## Alternatives considered

- **`llm-rubric` (LLM-as-judge) assertions instead of hand-written JS
  checks.** Considered for the Validator scenarios specifically. Rejected
  for now: it doubles LLM cost per scenario (a judge call per test case) and
  adds a second point of non-determinism on top of the one already being
  tested. The current JS assertions against schema shape plus one loose
  numeric bound already catch the regressions that matter (broken JSON
  output, an inverted or dropped instruction) without that cost. Worth
  revisiting once there's a track record of real prompt regressions this
  suite has caught, per `PROJECT_BRAIN.md`'s existing "tune thresholds once
  there's data" pattern for `SHORTLIST_THRESHOLD` etc.
- **Running promptfoo on every push, accepting the token cost.** Rejected —
  see "gated" reasoning above.
- **A hand-rolled pytest-based prompt eval instead of Promptfoo.** Rejected:
  Promptfoo is one of the three originally-named LLMOps tools this project
  set out to demonstrate; a hand-rolled equivalent would be technically
  sufficient but forfeits the actual portfolio point of using the named
  tool. (Contrast with Braintrust, which genuinely has no available key —
  a different situation, documented in `PROJECT_BRAIN.md` §7.)
- **Pushing built Docker images to a registry from `ci.yml`.** Deferred, not
  rejected: no registry is wired yet (see ADR-0007's "real deployment"
  consequence) — `ci.yml` builds images to validate the Dockerfiles stay
  correct but does not push, with a comment marking exactly where that would
  plug in once a target exists.

## Consequences

- `pyproject.toml` gained a `ruff` dev dependency and a `[tool.ruff]` config
  (target 3.13, line-length 110 with `E501` ignored — prompts and log
  messages legitimately run long — `E`/`F`/`I`/`B`/`UP` rule sets). First
  lint pass surfaced two real fixes beyond auto-fixable import sorting: an
  unqualified `zip()` in `build/graph.py`'s fan-out (`zip(..., strict=True)`
  now required by `B905`, correctly catching a latent silent-truncation risk
  if `components`/`results` ever mismatched in length) and
  `resilience.with_retry` converted from `TypeVar`-based to PEP 695 generic
  syntax (`with_retry[T](...)`) per `UP047`.
- A new `p2pops-promptfoo-provider` console script
  (`pyproject.toml`) makes the provider a stable, testable entry point
  rather than a bare script path.
- CI requires a GitHub remote to actually run — tracked as an explicit open
  item alongside deployment credentials in the Session Handoff, not silently
  assumed to exist.
