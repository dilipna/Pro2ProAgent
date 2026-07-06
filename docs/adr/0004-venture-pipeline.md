# ADR-0004: The venture pipeline — what happens after human approval

**Date:** 2026-07-06 · **Status:** Accepted

## Context

When the founder approves a shortlisted pain point at the email gate, the
system must transform it into a validated product opportunity — grounded in
evidence, not a single LLM's first idea. The original plan ("PM writes a
PRD") was too shallow for a venture-studio-grade outcome.

## Decision

A dedicated **venture subgraph** (`p2pops.venture`) runs once per approved
idea, recording into the same run timeline:

```
evidence → [validator ∥ ethnographer ∥ demand-analyst ∥ competitor-scout]
        → validation gate → solution architect → deterministic ranking
        → direction gate → red team ⇄ refiner (≤2 rounds) → strategist
        → dossier persisted (complete | rejected | parked)
```

Key design rules:

1. **LLM agents produce artifacts; code makes decisions.** Agents emit
   structured schemas with bounded sub-scores and cited evidence; ranking
   (weighted composite with saturation damping) and every go/no-go gate are
   deterministic Python (`venture/scoring.py`). Two runs over the same
   artifacts rank and gate identically — explainable, reproducible.
2. **Evidence before opinion.** A deterministic retrieval step (HN search +
   article extraction, no LLM) feeds all four analysis agents; they must
   cite items (E1, E2…) and report counter-signals. Thin evidence lowers
   confidence, which the validation gate enforces.
3. **Founder patterns as a curated corpus.** `venture/principles.py`
   distills transferable principles (Airbnb/Stripe/Canva/Notion/Duolingo/
   Figma/Slack/Shopify/Vercel) with applicability conditions and failure
   modes. The architect must argue *why* a principle transfers; the red
   team attacks via its documented failure mode. This keeps "learn from
   successful founders" deterministic and auditable rather than vibes.
4. **First-idea bias is designed against.** The architect must produce 4–6
   mechanically different directions plus explicitly rejected framings;
   ranking picks the winner, not the generation order.
5. **Bounded adversarial refinement.** Red team attacks through five lenses
   (technical/business/financial/operational/user) with concrete failure
   scenarios; the refiner must answer every critical/major issue or carry
   it as a named unresolved risk. At most `MAX_REFINEMENT_ROUNDS` (2), then
   the opportunity is **parked honestly** — a real venture studio kills
   ideas; so do we.
6. **Everything lands in one dossier.** `OpportunityDossier` (persisted on
   the `opportunities` row) holds every artifact, every gate result, every
   stress round — the full argument, not just the conclusion.
7. **Reliability**: temperature 0, bounded retries per agent call, clamping
   validators absorb out-of-range scores (Anthropic rejects min/max JSON
   schema constraints), per-idea failure containment in the runner.

## Testing strategy

All agent calls flow through one seam (`agents._structured`); tests replace
it with a deterministic fake and run the *real* graph end-to-end offline:
happy path (fail stress round 1 → refine → pass round 2 → vision), rejection
at the validation gate, and parking on exhausted refinements. Scoring and
gates have direct unit tests.

## Consequences

- A full venture run makes ~10–14 LLM calls per approved idea (Sonnet-class
  for architect/red-team/refiner/strategist, Haiku-class for analysis) —
  meaningful spend; the sequential per-idea execution in the runner is the
  cost-control knob.
- The dossier JSON is the contract for the web showcase (Phase 2 UI) and
  the console's opportunity views.
- Live LLM verification is pending an OpenRouter top-up (balance exhausted
  during Phase 1 verification); the offline graph tests carry correctness
  until then.
