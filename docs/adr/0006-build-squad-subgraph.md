# ADR-0006: The build-squad subgraph — scaffolding a completed opportunity

**Date:** 2026-07-06 · **Status:** Accepted

## Context

The venture pipeline (ADR-0004) produces a `complete` `OpportunityDossier` with
a full product vision, but nothing turns that vision into a starting point for
actually building it — the single biggest remaining gap versus the original
"discovery → build" vision. A second subgraph is needed: PM → Architect →
Engineer → QA, producing a scaffold artifact from one completed opportunity.

## Decision

A dedicated **build-squad subgraph** (`p2pops.build`) runs **manually**, once
per operator decision to scaffold a `complete` opportunity — never
automatically, unlike venture pipeline after human approval:

```
pm → architect → engineer (fan-out) → qa → [conditional]
                                        |
                    passed --------------+--- mark_complete ----> finish
                    failed & round<MAX -> revise -> qa (loop back)
                    failed & exhausted  -> mark_needs_revision -> finish
```

Key design rules:

1. **LLM agents produce artifacts; code makes decisions — including the file
   tree.** The Engineer is never given a `path` or `language` field; it only
   fills `content` for a file `build/scoring.py`'s `scaffold_target()` already
   chose from the component's `tech` string (keyword-matched). A hallucinated
   or unsafe path can never reach storage. This is the same split as venture's
   `SolutionDirection` (LLM) vs. `RankedDirection` (code).
2. **QA is a structured document review, not code execution.** Naming and
   docstrings say so explicitly (`QAReport`'s docstring) — there is no
   sandboxed test-running anywhere in this codebase to build on, and claiming
   otherwise would be dishonest about what the pipeline actually verifies.
3. **`asyncio.gather`, not LangGraph `Send`.** The fan-out over components is
   bounded, known at runtime, and non-recursive — exactly what venture's own
   4-way fan-out (fixed named nodes + `add_edge`) already does without `Send`.
   Introducing a second orchestration primitive (plus the `Annotated` reducer
   fields `Send` would require) buys nothing here. `gather(..., return_exceptions=True)`
   extends the same per-item failure containment `runner.execute_venture`
   already provides at the idea level down into Engineer's internal fan-out —
   one component's LLM error never aborts the whole build — and one AgentOps
   event is logged per component, not one summary event, keeping observability
   granularity consistent with every other stage.
4. **Bounded, honestly-surfaced revision.** `MAX_QA_ROUNDS = 2` (same
   convention as `MAX_REFINEMENT_ROUNDS`: the total number of QA rounds, so
   this means exactly one revision attempt) — `revise` re-invokes Engineer
   only for the components a critical `QAIssue` actually names. If QA names a
   component that doesn't exist (hallucinated/typo'd), or fails on verdict
   alone with no component-specific issue, the fallback is to redo *every*
   component rather than silently no-op. Exhausted revision yields
   `needs_revision`, never a silently-accepted `complete`.
5. **Manual trigger only — no public button.** The `/console` page is
   explicitly "Internal · read-only" and unauthenticated (`API_TOKEN` blank =
   open). The operator trigger is the `p2pops-build <opportunity_id>` CLI
   (blocking, mirrors how discovery has its own `p2pops-pipeline` CLI). A
   protected `POST /api/v1/builds` (behind the existing `require_operator`
   dependency, same tier as `POST /api/v1/runs`) exists too, for future
   automation — but no frontend code ever calls it. The frontend only ever
   reads build status/dossier, never writes.
6. **One dossier, one row.** `BuildDossier` mirrors `OpportunityDossier`'s
   shape: everything the build produced, persisted as one JSON blob on the
   `builds` table. `scaffold_files` holds only the *current* state (replaced
   wholesale per revised component); `qa_reports` is append-only across
   rounds — the argument for why a revision happened, not just the outcome.

## Testing strategy

Same seam as venture: all LLM calls flow through the one shared
`venture.agents._structured` function — `build/agents.py` calls it via
module-attribute access (`venture_agents._structured(...)`, not
`from ..venture.agents import _structured`), which is what lets a single
`monkeypatch.setattr` on `p2pops.venture.agents` intercept calls from *both*
packages. Tests replace it with a deterministic fake and run the real graph
offline: a clean pass, one revision round then clean, an exhausted revision
(`needs_revision`), and the unmatched-component-name fallback. Because
Engineer calls the LLM concurrently multiple times per run with the same
schema (`ScaffoldContent`) — the one agent in this codebase that does — the
fake dispatches on the component name embedded in the prompt, not schema type
alone.

## Consequences

- Worst-case LLM-call count (~16 at 6 components with one revision round) is
  already comparable to venture's own worst case (~10) despite being "one
  subgraph stage" — a direct consequence of Engineer's fan-out multiplying
  cost per QA round. `MAX_QA_ROUNDS` should not be raised without re-deriving
  this math (comment lives next to the constant in `build/scoring.py`).
- The scaffold is genuinely a *scaffold* — explicit TODOs, real structure, not
  a finished implementation. This is a deliberate, honest scope boundary, not
  an unfinished feature.
- `Build` has no `relationship()` on `Opportunity` (matches `Opportunity`'s own
  plain-FK precedent over `Run`/`Idea`) — always queried explicitly through
  `db/repository.py`, never assumed via ORM attribute access.
- The approval-email copy ("the build squad takes it from here") predated this
  subgraph and described the venture pipeline; it now reads "the venture
  pipeline takes it from here" to avoid describing a much-later, manually
  triggered stage as automatic.
