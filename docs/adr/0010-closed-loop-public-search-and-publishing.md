# ADR-0010: Closing the loop — auto-build, product publishing, and public keyword search

**Date:** 2026-07-11 · **Status:** Accepted

## Context

Through Phase A the pipeline stopped, in practice, at "validated": Discover
and Validate ran end to end, the human gate worked, the venture pipeline
produced dossiers — but the build squad ran only on manual CLI trigger, its
output was a DB-only scaffold with TODOs, and nothing ever became a live
product a visitor could click. The showcase's own copy ("Problems in.
Products out.") promised more than the system delivered. This ADR covers
the set of decisions that close Discover → Publish for real, plus the
public keyword-search entry point and its spend controls.

## Decisions

### 1. Approval auto-chains venture → build → publish (supersedes part of ADR-0006)

ADR-0006 made the build trigger CLI/protected-POST only, because `/console`
is unauthenticated and a public button would let visitors spend LLM budget.
That reasoning still holds — what changed is *which* human action gates the
spend. The human approval at the review gate **is** the authorization; a
second manual step between "approved" and "building" was a silent stall,
not a safety layer. `runner.resume_run` now chains every venture-`complete`
opportunity straight into `execute_build`. The CLI and protected POST
remain for re-builds. There is still no public build trigger anywhere.

### 2. The build target is a working client-side web MVP, not a scaffold

A "product" the showcase can honestly link to must work when opened. The
smallest deployable unit a small model can reliably produce end-to-end is a
self-contained static web app (HTML/CSS/JS, localStorage persistence, no
build step, no server, no external dependencies). PM/Architect/Engineer/QA
prompts all encode this constraint; the Architect designs exactly three
browser-file components. Server-side products stay out of v1 scope by
design — that's a scope decision, not a capability ceiling.

### 3. Engineers run sequentially with sibling files in context

The first live MVP build failed QA exactly the way a parallel fan-out
predicts: `app.js` referenced element ids `index.html` never defined. Files
that must interlock cannot be written blind against each other, so
`_run_engineer` now runs components sequentially in dependency order
(HTML → CSS → JS), passing every already-written file into the prompt;
revision rounds also see unrevised siblings. This deliberately retires
ADR-0006's `asyncio.gather` fan-out for the Engineer — ~10s of lost wall
time bought cross-file consistency, which is the difference between a
product and a pile of files. Per-component failure containment is
unchanged.

### 4. Publish is deterministic code with an honest failure mode

`publish.py` packages the QA-passed files (guarantees an `index.html`,
injects a small attribution badge linking back to the story page), deploys
via Vercel's deployment API under a deterministic project name
(`ptp-NNN-slug`), waits for READY, and smoke-checks the URL (200, HTML,
non-trivial body) before anything claims "Live". No `VERCEL_TOKEN`, no PTP
number, or any deploy/smoke failure → an event and a complete-but-
unpublished build; the showcase never says Live without a verified URL.

### 5. PTP numbers are assigned at shortlist time, in code

`PTP-XXX` is the public identity of a validated problem. Numbers are
assigned inside `repo.save_idea`'s transaction when the Analyst shortlists
(rejected/duplicate noise never burns one), sequentially, never reused.
1–3 stay reserved for the pre-database seeded showcase cards. Human-declined
ideas keep their number but leave the public showcase.

### 6. Public keyword search is an open endpoint with layered spend controls

`POST /api/v1/search` is deliberately unauthenticated — the feature is
"any visitor can point the pipeline at a topic." What it is *not* is a
public spend button: per-client hourly limit → 24h keyword dedupe → global
daily run cap → daily cost ceiling (from the `LlmCall` ledger) all run
before the first LLM token is spent, every submission is audited in
`search_requests` (hashed client id, never the raw IP), and a keyword-tuned
NeMo rail (separate from the idea rail, which would wrongly block short
topics as "too vague") screens the input. Everything a search starts still
flows through the same human gate; a visitor can surface candidates, only
the operator green-lights builds.

### 7. The console approval queue is a token-gated JSON twin of the email links

`GET /api/v1/reviews/pending` returns live approve/reject capabilities
(the review tokens), so it sits behind the operator bearer token; the
console UI takes the key per-session and proxies through the web tier.
The email path (ADR-0002) is unchanged and remains the fallback.

## Consequences

- The 8k-TPM builder model (ADR-0005's table) cannot carry whole product
  files; Engineer and QA moved to the 30k-TPM default tier. Revisit if the
  account's limits change.
- Schema changes are additive nullable columns applied by a SQLite
  micro-migration in `init_db` — the last stop before Alembic becomes
  mandatory.
- Sequential engineering makes build wall-time linear in component count;
  fine at 3 components, a real cost if that number grows.
