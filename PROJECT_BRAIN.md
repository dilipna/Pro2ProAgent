# PROJECT_BRAIN.md — ProToPro Single Source of Truth

> **How to use this file:** open a fresh Claude session and say "Read PROJECT_BRAIN.md and continue development." Everything needed to pick up work with zero prior context lives here. **Section 15 (Session Handoff) is the most important section and is updated at the end of every significant work session** — read it first if you're in a hurry.
>
> Last verified against the actual codebase: **2026-07-11** (Phase B session: full test suite 78/78, live end-to-end loop run, production URLs curled, deployed console confirmed "API connected"). Nothing in this document is aspirational unless explicitly marked "planned" or "not started."
>
> **This project is publicly deployed AND has shipped its first product.** Web: **https://protopro.vercel.app** (Vercel). API: **https://protopro-api.onrender.com** (Render, Docker-based, from `render.yaml`, auto-deploys on push to master). First pipeline-built product: **https://ptp-011-trustlayer-sdk.vercel.app** (story: `/showcase/ptp-011`).

---

## 1. Project Overview

**Name:** ProToPro ("Problem to Product"). Internal Python package/codename: `p2pops` (from the original working title "P2POps") — kept deliberately; renaming is pure churn with no functional value (see §10's decision log).

**Elevator pitch:** ProToPro is an autonomous product-discovery company run by AI agents. It listens for real, recurring pain points across developer communities (Hacker News today; Reddit deferred), validates each one through a guardrailed multi-agent analysis pipeline, pauses for a human's yes/no over email, and — on approval — runs the idea through a second multi-agent "venture pipeline" that produces evidence-grounded market analysis, a ranked set of solution directions, adversarial stress-testing, and a complete product vision. Two independent adversarial gates can and do kill weak ideas honestly (observed live, see §15).

**Vision:** A venture-studio-in-a-box: point it at a domain, let a company of specialized agents do discovery → validation → opportunity synthesis, with a human as the single approval gate and full observability into every agent's reasoning.

**Mission (near-term, honest):** This is currently a **portfolio/demonstration project**, explicitly positioned (per the user's direction) to prove hands-on 2026-grade LLMOps/AgentOps engineering skill for job applications (AI Engineer / LLM Engineer / Applied AI / Agentic AI / MLOps roles). It is built to production engineering standards (typed schemas, tested gates, real retry/observability logic, ADR-documented decisions) and, as of Phase A, is **actually deployed and publicly reachable** (see the banner at the top of this file) — though it still has no real users and no revenue; the point of the deployment is to prove the engineering, not to launch a business.

**Target users (of the eventual product):** founders/venture-studio operators who want AI-assisted opportunity discovery. **Target users (of the project right now):** recruiters and engineers evaluating the codebase, via the public site's Showcase and the discreet `/console` operations view.

**Core problem being solved:**
1. *(Product-level)* Good product opportunities are hiding in plain sight in developer communities; finding, validating, and stress-testing them well is slow, unstructured, and expert-scarce.
2. *(Portfolio-level)* Prove — with a live, working, adversarially-tested system, not slideware — that the builder can design multi-agent orchestration, guardrails, evaluation gates, HITL workflows, and production-shaped observability.

**Resume/interview value proposition:** every piece was chosen to map directly onto a 2026 AI-engineering job description line item: LangGraph orchestration with real conditional routing and a bounded adversarial refinement loop; NeMo Guardrails; a swappable multi-provider LLM layer (Anthropic/OpenRouter/Groq) that survived three real capacity/quota incidents live; a from-scratch rate-limit-aware retry layer with 9 unit tests; async SQLAlchemy + FastAPI + SSE; LangGraph `interrupt()`-based human-in-the-loop with signed single-use tokens; a deterministic, explainable scoring/gating model (not "the LLM decides"); and a fully custom-designed Next.js frontend. See §15 for the specific live incidents and fixes — these are genuine debugging stories, not invented ones, and make excellent interview material.

---

## 2. Repository Analysis

### What currently exists (verified by direct file inspection, 2026-07-07)

**Backend** (`src/p2pops/`, Python 3.13, `uv`-managed):
- A discovery pipeline: Research Agent (LangGraph ReAct agent, tools served over a real MCP stdio server) → Supervisor routing → Analyst (NeMo Guardrails input rail → ChromaDB semantic dedupe → structured LLM scoring).
- A run-infrastructure layer: async SQLAlchemy models, a repository module, a FastAPI service, SSE event streaming.
- An email-based human-in-the-loop gate built on LangGraph's `interrupt()` + a SQLite checkpointer, with signed single-use review-action links.
- A **venture pipeline**: a second LangGraph subgraph that runs once per human-approved idea — parallel evidence-grounded analysis, a curated founder-pattern principle library, deterministic ranking, a bounded red-team/refiner adversarial loop, and a final product-vision synthesis, persisted as a structured `OpportunityDossier`.
- A **build-squad subgraph**: PM → Architect → Engineer (fan-out) → QA → bounded revise, scaffolding a `complete` opportunity on manual trigger.
- A from-scratch LLM-call resilience layer (rate-limit-aware retry, provider-error classification) built and hardened against **real, live provider failures**, not hypothetical ones.
- **LLM cost tracking** (Phase A): a global `LlmCall` ledger + a list-price table, capturing real token usage/estimated cost at every structured-output call site, exposed via `GET /api/v1/costs` and a console panel.
- `GET /api/v1/health`: an end-to-end database probe (not a liveness stub) — the target for every container/orchestrator healthcheck.

**Frontend** (`web/`, Next.js 16 + TypeScript + Tailwind v4 + Motion, pnpm):
- A fully custom-designed public landing page ("obsidian & ember" design system) telling the problem→product story, with a live discovery ticker seeded from real pipeline output.
- A discreet `/console` operations page for recruiters, showing pipeline module status, a live run-store metrics strip, run/opportunity deep views, and an LLM cost panel.
- **Wired to the live backend API** (Phase 2, now against the deployed production API): a server-side API client (`web/src/lib/api.ts`) feeds the hero ticker, Showcase, pipeline stats, console metrics, and cost panel from `/api/v1/*`, with the seeded content retained as an automatic fallback whenever the API is unreachable — the public site never breaks because the backend is down.

**Infrastructure (Phase A, 2026-07-07 — new since the last verification)**:
- Multi-stage Docker images for both tiers (`Dockerfile`, `web/Dockerfile`), a working `docker compose up --build`, and a `docker-compose.dev.yml` hot-reload override.
- Kubernetes manifests (`deploy/k8s/`) behind one kustomization — a namespace, ConfigMap, Secret template, API Deployment+PVC+Service, web Deployment+Service+HPA, and an Ingress.
- GitHub Actions CI (`.github/workflows/ci.yml` on every push: lint/test/build/docker-build/promptfoo-schema; `.github/workflows/promptfoo.yml` manual+weekly for real LLM-call regression testing).
- A Promptfoo prompt-regression suite (`promptfooconfig.yaml` + `src/p2pops/evals/promptfoo_provider.py`) that calls the REAL agent functions, not copied prompts — live-verified 5/5 against Groq.
- **Actually deployed**: web on Vercel (`https://protopro.vercel.app`), API on Render (`https://protopro-api.onrender.com`, driven by `render.yaml`), wired together and confirmed live.

**Docs**: `docs/adr/` (9 ADRs — see §4's decision list), `implementation-notes.md` (a chronological phase log kept during development).

### Strengths
- Real, live-verified correctness, not just passing unit tests: the entire chain (discover → analyze → email → approve → venture-pipeline → dossier) has been run against real hosted LLM APIs end to end, and the failures encountered along the way were root-caused and fixed, with tests added to prevent regression. This is a materially stronger portfolio signal than a project that only ever ran against mocks.
- Deterministic, explainable decision-making layered on top of LLM outputs: `venture/scoring.py` computes ranking and gate pass/fail in plain Python from LLM-supplied sub-scores — reproducible, unit-tested, and not "vibes."
- Every non-obvious engineering decision is written down as an ADR with the reasoning and trade-offs, not just the outcome (9 ADRs as of Phase A).
- Test suite (56 tests) covers unit logic (scoring, resilience classification, pricing), integration (repository, hermetic ASGI API tests, cost aggregation), and full offline graph execution — a good testing pyramid.
- **Actually deployed and publicly reachable**, not just "deployment-ready." The Docker/K8s/CI work was verified by running it (containers built and started healthy, a live promptfoo run, a live pipeline run against the deployed API whose cost data rendered in the deployed console) — the same "live-verify, don't just wire" discipline applied to every prior phase.

### Weaknesses / gaps (see §3 and §12 for the full itemized list)
- No Reddit source (deferred by explicit user choice, HN-only).
- `llm.py`'s single-caller `complete()` function has no retry/resilience wrapping (documented, deliberate, low-risk gap).
- Cost ledger is global, not run-scoped (deliberate scope call, ADR-0009).
- Render's free/starter tier means the production API can cold-start or (on the true free tier) lose its SQLite data on redeploy — see §8 for the exact trade-off made.
- No authentication beyond an optional bearer token — now genuinely relevant since the API has a real public URL, not just a local one (see §12).

---

## 3. Current Project Status

### Completed
- Milestones 1–3 (pre-pivot): Research Agent + MCP server, Supervisor + Analyst with guardrails/dedupe/scoring, all live-verified.
- Phase 0.5: web foundation, design system, landing page, console shell.
- Phase 1: async DB layer, email HITL gate, FastAPI service, venture pipeline (all agents, scoring, gates, dossier).
- Phase 1.5: Groq provider integration, full LLM-call resilience layer, 5 real bugs found/fixed via live iteration, first fully clean live run of the entire chain including 2 honest parks and 1 complete product vision.
- Phase 2: frontend wired to the live API — server-side client with timeout + seeded fallback, ISR on the landing page, force-dynamic console with a live metrics strip. Verified live in both the API-up and API-down states.
- Phase 3: LangSmith/Logfire verified live via API (not just wired); a first eval (`p2pops-eval`, dependency-free); the **build-squad subgraph** (PM → Architect → Engineer → QA) shipped and live-verified against a real opportunity; console deep views (`/console/runs/[id]`, `/console/opportunities/[id]`) rendering the full event timeline and dossier/scaffold, read-only.
- **Phase A (2026-07-07): production foundation, complete.** Docker (both tiers, multi-stage, verified via `docker compose up`), Kubernetes manifests (`deploy/k8s/`, rendered clean via kustomize), GitHub Actions CI/CD (lint/test/build/docker/promptfoo-schema on every push; a separate manual/weekly workflow for live promptfoo evals), Promptfoo prompt-regression suite (5/5 live against Groq, calling the real agent functions), LLM cost tracking (ledger + pricing table + console panel, live-verified against a real pipeline run), and — new this session — **actual public deployment**: web on Vercel, API on Render, wired together and confirmed live end-to-end (see the banner at the top of this file for URLs).
- **Phase B (2026-07-11): the closed loop + public search + real console data (ADR-0010).** Approval now auto-chains venture → build squad → publish; the build squad ships working client-side web MVPs (sequential engineers with sibling-file context, deterministic asset linker) and `publish.py` deploys them to their own Vercel URL with a post-deploy smoke check; PTP numbering is a database fact assigned at shortlist time; a public keyword-search endpoint runs scoped discovery behind layered spend controls; the console gained an operator approval queue, SSE live run timelines, keyword tags, and a daily cost-ceiling alert; every PTP item has a permanent story page. See §15 for exactly what was live-verified vs. shipped-but-gated.

### In Progress / Partially Implemented
- **Build-squad scaffolds are DB-only** — real, inspectable content, but nothing writes the scaffold to an actual directory on disk yet.
- **Console depth**: run timelines, opportunity/build dossiers, and the LLM cost panel all render in the UI now; there's still no real visual graph-state representation (the run timeline is a linear list, not a graph) — the natural next UI milestone.

### Planned (explicitly discussed, not started)
- Real file-tree persistence for build-squad scaffolds (currently DB-JSON-only).
- Postgres migration, to unlock horizontal API scaling (currently deliberately 1 replica everywhere — SQLite is single-writer, see §8).
- A visual agent-execution graph in the console (beyond the linear event timeline).

### Missing
- Reddit as a second discovery source (PRAW) — deferred by explicit choice.
- Any authentication/authorization beyond the optional single bearer token — see §12, now a real (not hypothetical) gap since the API has a public URL.
- Postgres migration (SQLite is the only datastore; fine at current scale, explicitly logged as a deviation to revisit).
- Real Braintrust integration (the homegrown eval is a deliberate stand-in — no `BRAINTRUST_API_KEY` exists).

### Blocked
- Nothing is currently blocked. (Historical note: Anthropic-direct and OpenRouter both ran out of credit/balance during development; Groq is the working live provider as of this writing, see §7 and ADR-0005.)

### Overall completion estimate
Roughly **90–95% of a "flagship" version** of this project. Every one of the originally-named LLMOps stack tools (LangGraph, NeMo Guardrails, LiteLLM/multi-provider, LangSmith, Logfire, Promptfoo) now has a working, live-verified implementation; the homegrown eval is an honest, documented stand-in for Braintrust specifically (no key available). Docker, CI/CD, Kubernetes, and — as of this session — **actual public deployment** are all done and live-verified, not just "ready." What's left is genuinely optional polish (Postgres for horizontal scaling, real file-tree persistence for scaffolds, a visual execution graph) rather than missing core capability.

---

## 4. Architecture

### High-level architecture

```
                         ┌─────────────────────────────────────────┐
                         │              FastAPI service             │
                         │              (p2pops-api)                 │
                         │  /api/v1/runs, /ideas, /opportunities,    │
                         │  /stats, SSE stream · /r/{token}/{action} │
                         └───────────────┬───────────────────────────┘
                                         │
                    ┌────────────────────┼─────────────────────┐
                    │                    │                     │
             runner.py (owns          db/repository.py    notify.py
             AsyncSqliteSaver          (async SQLAlchemy    (email HITL:
             checkpointer, thread_id   over runs/events/    Console/Resend
             = run_id)                 ideas/reviews/opps)  adapters)
                    │
     ┌──────────────┴───────────────────────────────────────────┐
     │  graph.py — discovery pipeline (checkpointed)             │
     │                                                             │
     │  research ──▶ analyst ──▶ request_review ──▶ human_gate    │
     │  (LangGraph    (guardrails,    (creates review    (interrupt(),│
     │   ReAct agent,  Chroma dedupe,  tokens, sends       pauses for │
     │   MCP tools)    structured      email)              real)     │
     │                 scoring)                              │       │
     │                                                        ▼       │
     │                                                    finalize    │
     └────────────────────────────────────────────────────────┬──────┘
                                                                │ on approval,
                                                                │ per approved idea
                                                                ▼
     ┌──────────────────────────────────────────────────────────────┐
     │  venture/graph.py — opportunity validation (stateless per run) │
     │                                                                 │
     │  evidence ──▶ [validator ∥ ethnographer ∥ demand ∥ scout]       │
     │      ──▶ validation_gate (code) ──▶ architect ──▶ rank (code)  │
     │      ──▶ direction_gate (code) ──▶ stress ⇄ refine (≤2 rounds) │
     │      ──▶ vision ──▶ finish (persists OpportunityDossier JSON)  │
     └──────────────────────────────────────────────┬────────────────┘
                                                      │ manual trigger only:
                                                      │ `p2pops-build <opportunity_id>`
                                                      │ or protected POST /api/v1/builds
                                                      ▼
     ┌──────────────────────────────────────────────────────────────┐
     │  build/graph.py — build-squad (stateless, manually triggered)  │
     │                                                                 │
     │  pm ──▶ architect ──▶ engineer (asyncio.gather, N components)  │
     │      ──▶ qa (code gate) ──▶ complete                            │
     │                        └──▶ revise (≤1 round) ──▶ qa            │
     │                        └──▶ needs_revision (exhausted)          │
     │      ──▶ finish (persists BuildDossier JSON on `builds` row)   │
     └──────────────────────────────────────────────────────────────┘
```

### Folder structure (backend)

```
src/p2pops/
  agents/          research.py (ReAct + MCP), analyst.py (guardrail→dedupe→score)
  api/              app.py (FastAPI app + routes), schemas.py (pydantic I/O models)
  db/               models.py (SQLAlchemy ORM), engine.py, repository.py
  mcp/              server.py (FastMCP server: search_hacker_news, read_article)
  tools/            hn.py (HN Algolia search), web.py (article text extraction)
  venture/          agents.py, graph.py, principles.py, schemas.py, scoring.py
  build/            agents.py, graph.py, schemas.py, scoring.py (build-squad, ADR-0006)
  evals/            analyst_eval.py (Analyst-vs-human agreement report), promptfoo_provider.py (ADR-0008)
  chat_model.py     provider-agnostic LangChain chat model factory (+ resolve_model, ADR-0009)
  config.py         pydantic-settings Settings (env-driven, blank-string-safe)
  cost_tracking.py  best-effort LLM usage capture, the seam every call site feeds (ADR-0009)
  graph.py          discovery pipeline StateGraph
  guardrails.py     NeMo Guardrails input rail wrapper
  llm.py            plain LiteLLM completion wrapper (bootstrap check only)
  memory.py         ChromaDB semantic dedupe
  models.py         shared pydantic schemas (DiscoveredIdea, AnalyzedIdea, ...)
  notify.py         email HITL notifier (Console/Resend adapters)
  pipeline.py       CLI entrypoint for a single discovery run
  build_cli.py      CLI entrypoint for a single build-squad run
  pricing.py        USD/token rate table + cost estimation (ADR-0009)
  resilience.py     rate-limit-aware retry (the resilience layer, ADR-0005)
  runner.py         run lifecycle: start/execute/resume, owns the checkpointer
  telemetry.py      LangSmith + Logfire wiring

web/src/
  app/              page.tsx (landing), console/page.tsx, layout.tsx, globals.css
  app/console/      runs/[id]/page.tsx, opportunities/[id]/page.tsx (read-only deep views)
  components/       nav, hero, method, showcase, pipeline-stats, footer, reveal
  lib/api.ts        server-side /api/v1 client (timeout + seeded-fallback)
  lib/cases.ts      hand-seeded showcase content (real pipeline output, static)

Infra (repo root, Phase A):
  Dockerfile, web/Dockerfile     multi-stage images (ADR-0007)
  docker-compose.yml / .dev.yml  local one-command startup + hot-reload override
  deploy/k8s/                    namespace, ConfigMap, Secret template, api/web manifests, Ingress, kustomization
  deploy/README.md               3-tier deploy guide (Compose / K8s / managed PaaS)
  render.yaml                    Render Blueprint — the API's actual deploy target
  .github/workflows/ci.yml       lint/test/build/docker/promptfoo-schema, every push, zero LLM calls
  .github/workflows/promptfoo.yml manual + weekly, real LLM calls, skips gracefully without a key
  promptfooconfig.yaml           5 live-verified prompt-regression scenarios
```

### Data flow
1. `POST /api/v1/runs {topic}` → `runner.start_run` creates a `Run` row, launches `execute_run` as a background asyncio task.
2. `execute_run` invokes the compiled discovery graph (checkpointed by `thread_id=run_id`). Every node appends `RunEvent` rows — this *is* the AgentOps timeline.
3. On reaching ideas worth reviewing, `request_review` creates one `Review` row (a signed random token) per shortlisted `Idea`, emails a summary (or logs it, if no Resend key), and the graph pauses at `human_gate` via `interrupt()`.
4. A human clicks `/r/{token}/approve` or `/reject` → `record_decision` consumes the token (single-use, expiring) and updates the `Idea` status.
5. Once every review for a run is decided, `maybe_resume_after_decision` fires `resume_run`, which resumes the checkpointed graph with `Command(resume=decisions)`.
6. For every **approved** idea, `runner.execute_venture` runs the venture subgraph sequentially (deliberately sequential — a concurrency/cost control knob, not an oversight), producing an `Opportunity` row with the full `OpportunityDossier` JSON.
7. The API and frontend read all of this back through `/api/v1/runs`, `/ideas`, `/opportunities`, `/stats`, `/costs`, and the SSE stream — live-wired since Phase 2, now against the deployed production API.
8. On a `complete` opportunity, an operator may manually run `p2pops-build <opportunity_id>` (or the protected `POST /api/v1/builds`) — `runner.execute_build`/`start_build` drives the build-squad subgraph, producing a `Build` row with the `BuildDossier` JSON. Never automatic; the console never exposes a trigger button.
9. Every structured-output LLM call (Analyst scorer, all venture/build agents via `_structured`, Research's per-message ReAct capture) also feeds `cost_tracking.record_usage` → an `LlmCall` row — best-effort, never able to break the pipeline it's observing (ADR-0009).

### Memory architecture
Two distinct, deliberately different memory systems — do not conflate them:
- **ChromaDB** (`memory.py`): semantic dedupe only. Local `all-MiniLM-L6-v2` ONNX embeddings (no API key/cost), cosine distance, threshold empirically tuned (0.3) against real near-duplicate vs. unrelated problem statements. Answers "have we seen this idea before?"
- **LangGraph checkpointer** (`AsyncSqliteSaver`, in `runner.py`): the discovery graph's own execution state, keyed by `thread_id=run_id`. This is what makes the email-based pause-and-resume actually durable across process restarts — not a general-purpose memory system, specific to one pipeline's control flow.
- There is **no long-term "agent memory"** beyond these two (e.g., no cross-run learning, no vector store of past `OpportunityDossier`s for the venture agents to draw on yet — a real gap, see §12).

### Technology stack (verified from `pyproject.toml` / `web/package.json`)

| Layer | Tool | Status |
|---|---|---|
| Orchestration | LangGraph 1.2.7 | Live, both graphs |
| Tool protocol | MCP (`mcp` 1.28.1) + `langchain-mcp-adapters` | Live |
| Guardrails | NeMo Guardrails 0.23 | Live |
| Model routing | LiteLLM 1.91 (plain calls) + native LangChain clients (agentic calls) | Live |
| LLM providers | Anthropic direct, OpenRouter, Groq — swappable via `LLM_PROVIDER` | Groq is the working live provider |
| Vector memory | ChromaDB 1.5.9 | Live |
| API | FastAPI 0.139 + `sse-starlette` | Live |
| DB | SQLAlchemy 2.0 (async) + `aiosqlite` | Live, SQLite |
| Email | Resend (HTTP) / console fallback | Live (console adapter used in all testing so far) |
| Observability | LangSmith, Pydantic Logfire | **Live, verified** — a real run's traces confirmed via the LangSmith REST API (matching run IDs/timestamps) and Logfire's own successful-auth project URL, both 2026-07-06 |
| Evals | Braintrust (not integrated), homegrown eval, **Promptfoo** | `p2pops-eval`: Analyst-vs-human agreement report — live, dependency-free (no Braintrust key). **Promptfoo**: `exec:` provider calling the real agent functions, 5/5 live-verified against Groq (ADR-0008) |
| Cost tracking | Homegrown `LlmCall` ledger + `pricing.py` | **Live, verified** — real token usage/estimated cost captured at every structured-output call site, exposed via `/api/v1/costs` + a console panel (ADR-0009) |
| Frontend | Next.js 16, Tailwind v4, Motion | Live, wired to the deployed production API (seeded fallback when offline) |
| Containers | Docker (multi-stage, both tiers), Docker Compose | **Live, verified** — `docker compose up --build` runs both tiers healthy (ADR-0007) |
| Orchestration (optional) | Kubernetes manifests (`deploy/k8s/`) | Rendered clean via kustomize; not applied to a live cluster (none available locally) — see §8 |
| CI/CD | GitHub Actions | **Live** — `ci.yml` on every push, `promptfoo.yml` manual/weekly (ADR-0008) |
| Deployment | Vercel (web) + Render (API) | **Live, publicly deployed** — see the banner at the top of this file |
| Package mgmt | `uv` (Python), `pnpm` (Node) | — |

### Design patterns in use
- **Supervisor / conditional routing** (LangGraph `add_conditional_edges`), not a fixed linear pipeline.
- **Code-owns-decisions, LLM-owns-artifacts**: every ranking and gate in the venture pipeline is deterministic Python over LLM-supplied structured sub-scores — the core anti-"vibes" architectural choice of the whole system.
- **Port/adapter** for email delivery (`EmailNotifier` protocol, Console/Resend implementations) and implicitly for LLM providers (`chat_model.get_chat_model`).
- **Single retry seam** (`resilience.with_retry`) rather than scattered try/excepts.
- **Repository pattern** for all DB access (`db/repository.py`) — no ORM calls outside it.

### Important architectural decisions and why (full detail in `docs/adr/`)
- **ADR-0001**: Streamlit was the original UI plan; reversed in favor of a fully custom Next.js frontend, because the "premium SaaS, not AI-template" design bar cannot be hit with Streamlit's rerun model.
- **ADR-0002**: HITL happens over email with signed single-use links, not a web review UI — deliberate, since the founder explicitly did not want a public-facing review workflow.
- **ADR-0003**: above-the-fold content must be CSS-animated, never dependent on JS hydration to become visible (a real bug was caught and fixed this way).
- **ADR-0004**: the venture pipeline's full design — why code (not LLMs) makes gate/ranking decisions, why a curated principle library grounds the architect agent, why the refinement loop is bounded and parks rather than loops forever.
- **ADR-0005**: the resilience layer and Groq model choice — five real live bugs, root-caused and fixed, not papered over. This is arguably the single most interview-relevant document in the repo.
- **ADR-0006**: the build-squad subgraph — why the LLM never chooses a scaffold file's path/language (code does, from a keyword-matched heuristic), why `asyncio.gather` over LangGraph `Send`, why QA is a structured document review not code execution, why the trigger is CLI/protected-POST only with no public button.
- **ADR-0007**: containerization and deployment strategy — why K8s exists but isn't the primary deploy target (Vercel + a single container host is), why the API is pinned to 1 replica (SQLite is single-writer) while web gets an HPA, the `data_dir` URL-parsing bug found by containerizing.
- **ADR-0008**: CI/CD pipeline and Promptfoo — why prompt regression is a separate manual/weekly workflow (never on every push — real LLM calls cost money), why the Promptfoo provider calls the actual agent functions instead of copied prompts, the live test-design gap found and fixed during verification.
- **ADR-0009**: LLM cost tracking — why the ledger is global not run-scoped, the `include_raw=True` trap that would have silently regressed ADR-0005's retry contract if left unhandled, why pricing is an estimate against list price, not a bill reconciliation.

---

## 5. Features

| Feature | Status | Dependencies | Related agents | Future improvements | Priority |
|---|---|---|---|---|---|
| HN-based problem discovery | Done, live | HN Algolia API (keyless) | Research Agent | Add Reddit (PRAW) as a second source | Medium |
| Article enrichment | Done, live | httpx + BeautifulSoup | Research Agent (via MCP tool) | — | Low |
| Guardrailed idea validation | Done, live | NeMo Guardrails | Analyst | Add output rails, not just input | Low |
| Semantic dedupe | Done, live | ChromaDB | Analyst | Cross-run learning / trend detection | Medium |
| Idea scoring | Done, live | structured LLM call | Analyst | — | Low |
| Email HITL gate | Done, live | Resend/console, LangGraph interrupt | — (human) | Real email delivery (Resend key not yet supplied) | High |
| Venture opportunity pipeline | Done, live | 4 parallel agents + architect + red team + refiner + strategist | All venture/ agents | Persist evidence retrieval as reusable context across ideas | High |
| Deterministic scoring/gates | Done, tested | `venture/scoring.py` | — (code) | Tune weights against real outcomes once there's a track record | Medium |
| LLM-call resilience | Done, tested | `resilience.py` | All agents | Extend to `llm.py`'s `complete()` | Low |
| Public landing page | Done, live-wired (ISR, seeded fallback) | Next.js + `/api/v1` | — | Deeper showcase interactivity | Low |
| Operations console | Done, live metrics + run/opportunity deep views (read-only) | Next.js + `/api/v1` | — | Per-agent cost view; live graph state visualization | Medium |
| Build-squad product MVPs (was: scaffolding) | **Done — ships working client-side web apps; auto-runs after approval** | PM/Architect/Engineer/QA (`build/`), ADR-0010 | build-squad agents | Raise pass-rate further; server-side product tier someday | High |
| Product publishing (Vercel + smoke check) | **Done** (`publish.py`) | `VERCEL_TOKEN` | — (deterministic code) | Custom domains; deploy provider abstraction | High |
| Public keyword search (scoped discovery) | **Done, live-verified** | `POST /api/v1/search`, `search_requests` table, keyword rail | Research/Analyst + guardrail | Semantic (not just exact) keyword dedupe | High |
| PTP numbering + showcase lifecycle + story pages | **Done** | `ideas.ptp_number`, `/api/v1/showcase*` | — | — | High |
| In-console approval queue | **Done** | `/api/v1/reviews/pending` (operator-token) | — (human) | — | High |
| Console SSE live timeline + cost ceiling alert | **Done** | SSE proxy, `today_usd`/ceiling in `/costs` | — | Visual graph state (still open) | Medium |
| Evals (homegrown) | **Done, live** | `evals/analyst_eval.py` | — (code) | Wire to Braintrust if a key becomes available; grow past N=9 | Medium |
| Prompt regression (Promptfoo) | **Done, live-verified 5/5** | `promptfooconfig.yaml` + `evals/promptfoo_provider.py` | Analyst, Validator | Extend to Architect/Red Team/build-squad scenarios | Medium |
| LLM cost tracking | **Done, live-verified** | `cost_tracking.py`, `pricing.py`, `LlmCall` table | All structured-output call sites | Run-scoped cost view (currently global); real per-provider billing reconciliation | Medium |
| Docker / Compose | **Done, live-verified** | `Dockerfile`, `web/Dockerfile`, `docker-compose.yml` | — | — | — |
| Kubernetes manifests | **Done** | `deploy/k8s/` | — | Apply to a real cluster once one exists; currently only kustomize-rendered | Low |
| CI/CD (GitHub Actions) | **Done, live** | `.github/workflows/` | — | Add automated deploy trigger to Render/Vercel on merge | Medium |
| **Public deployment** | **Done, live** | Vercel (web), Render (API) | — | Postgres migration to unlock horizontal API scaling | High |

---

## 6. Multi-Agent System

Every agent below is a **real, separately invoked, separately traceable unit** — not a single mega-prompt.

### Discovery pipeline agents

**Research Agent** (`agents/research.py`)
- Responsibility: given a topic, find concrete, sourced AI-related problems.
- Inputs: a topic string.
- Outputs: `ResearchReport` (structured, via `response_format`) — a list of `DiscoveredIdea{title, description, source_url}`.
- Tools: `search_hacker_news`, `read_article`, served over a **real MCP server** (`mcp/server.py`, stdio transport) — this is genuine tool-use-over-a-protocol, not an in-process function call dressed up.
- Memory: none (stateless per call).
- Orchestration: LangGraph `create_react_agent`, `MAX_RESEARCH_STEPS=16` hard ceiling (sized against a measured mandatory-minimum path plus real observed small-model variance — see ADR-0005).
- Failure handling: `resilience.with_retry` wraps the whole agent turn; a 429 mid-loop retries the entire turn (tool calls are idempotent, so this only costs repeated work, never incorrect results); a step-ceiling trip (`GraphRecursionError`) is never retried (deterministic).
- System prompt explicitly requires a real, non-null `source_url` traced to an actual search result for every reported idea (a live bug — the model synthesizing a sourceless "meta-observation" idea — was fixed this way, not by weakening the schema).

**Analyst Agent** (`agents/analyst.py`)
- Responsibility: guardrail-check, dedupe-check, and score one discovered idea.
- Inputs: one `DiscoveredIdea`.
- Outputs: `AnalyzedIdea{..., score, reasoning, status}` where `status ∈ {rejected, duplicate, shortlisted}`.
- Tools/dependencies: `guardrails.is_idea_allowed` (NeMo Guardrails self-check-input flow, domain-specific prompt), `memory.find_duplicate` (ChromaDB), a structured scoring LLM call (`IdeaVerdict`).
- Deliberately **not** a LangGraph tool-calling agent — it's a plain async pipeline function, because that's the honest shape of what it does (a fixed sequence of checks, not open-ended tool use). Still fully traced (`logfire.span`).
- Failure handling: both the guardrail check and the scoring call go through `with_retry` independently.
- Success criteria / quality gate: `SHORTLIST_THRESHOLD=50` (module constant, not yet user-configurable — logged as a deliberate, revisit-later decision).

**Supervisor** (`graph.py`, `supervisor_node`)
- Currently a no-op node — exists as the seam where real routing logic (e.g., "too few ideas, broaden the topic and re-search") will grow. Honest about its current triviality rather than pretending it does more than it does.

### Venture pipeline agents (`venture/agents.py`, `venture/graph.py`)

All share a uniform contract: **structured input context (idea + upstream artifacts) → exactly one structured output schema, never free text**; temperature 0; routed through `venture.agents._structured` (the single LLM-call seam, wrapped by `resilience.with_retry`, and the exact seam tests substitute to run the whole graph offline). Since Phase A, `_structured` also feeds `cost_tracking.record_usage` — every venture and build-squad call (both packages share this one seam, ADR-0006) is captured in the `LlmCall` ledger for free.

| Agent | Inputs | Output schema | Success criteria (from the agent's own instructions) |
|---|---|---|---|
| Evidence gatherer | idea title/description | `EvidenceBundle` (deterministic — no LLM call at all: real HN search + article fetch) | Real, citable external evidence, or an honest "none retrieved" |
| Validator | context + evidence | `ProblemValidation` | Verdict grounded in cited evidence; honest counter-signals even when positive; confidence reflects evidence quality |
| Ethnographer | context + evidence | `SegmentAnalysis` | Segments distinct and reachable; primary chosen by pain × reachability, not size alone |
| Demand Analyst | context + evidence | `DemandAssessment` | Every signal traceable to evidence; no fabricated TAM numbers |
| Competitor Scout | context + evidence | `CompetitorLandscape` | Covers tools AND workarounds; names a specific, aimable "unserved gap" |
| Architect | all of the above + curated principle library | `DirectionSlate` (4-6 directions + explicitly rejected framings) | Directions differ in *mechanism*, not features; each cites a transferable principle and argues the transfer; conservative sub-scores |
| **Ranking** | `DirectionSlate` | `list[RankedDirection]` | **Not an agent — deterministic code** (`scoring.rank_directions`): weighted composite with saturation damping, stable tie-break |
| Red Team | chosen direction (+ prior refinement) | `StressTestReport` | Attacks from 5 lenses with concrete failure scenarios, not vague worry; honest severities; verdict follows from its own issues |
| Refiner | direction + stress report | `RefinedDirection` | Every critical/major issue answered by a change or explicitly carried as an unresolved risk — never silently dropped |
| Strategist | direction + segments + landscape + unresolved risks | `ProductVision` | A stranger understands the one-liner in 5 seconds; positioning vs. the *real* alternative; concrete 90-day execution plan |

**Orchestration**: parallel fan-out (`validate`/`segments`/`demand`/`landscape` all fire off `evidence` simultaneously) → deterministic `validation_gate` → `architect` → deterministic `direction_gate` → **bounded adversarial loop** (`stress` ⇄ `refine`, `MAX_REFINEMENT_ROUNDS=2`) → `vision` → `finish` (persists the dossier regardless of outcome — `complete`, `rejected`, or `parked` are all first-class, inspectable results).

**State management**: `VentureState` (a `TypedDict`) accumulates every artifact and every `GateResult` across the whole run — the persisted `OpportunityDossier` is essentially this state, serialized. Nothing is thrown away, including failed stress rounds.

**Failure handling**: per-idea containment in `runner.execute_venture` — one idea's venture pipeline throwing an unhandled exception does not take down the others or the parent run; it's recorded as an `opportunity.status="failed"` with an error event.

### Build-squad agents (`build/agents.py`, `build/graph.py`) — ADR-0006

Runs manually (CLI `p2pops-build <opportunity_id>`, or protected `POST /api/v1/builds`) against one `complete` `OpportunityDossier` — never automatically. Same LLM-call seam as venture (`build/agents.py` calls `venture_agents._structured(...)` via module-attribute access, not a re-import, so the one shared seam covers both packages).

| Agent | Inputs | Output schema | Success criteria (from the agent's own instructions) |
|---|---|---|---|
| Product Manager | opportunity vision/direction/segments/landscape | `BuildPlan` (3-8 features, tech stack, non-goals) | P0-first prioritization; acceptance criteria concrete enough to build against; explicit non-goals bound scope |
| Architect | `BuildPlan` | `ArchitectureSpec` (3-6 components + data model + API surface) | Every P0 feature covered by some component; `tech` named plainly enough to be keyword-matchable |
| Engineer | one `ComponentSpec` at a time (fan-out) | `ScaffoldContent` (content only — **never** path/language) | Real structure with explicit TODOs, not a placeholder comment; consistent with the shared data model |
| **Scaffold targeting** | `ComponentSpec.tech` | `(path, language)` | **Not an agent — deterministic code** (`scoring.scaffold_target`): keyword-matched, so the LLM can never choose an unsafe or arbitrary path |
| QA | plan + architecture + all scaffold files | `QAReport` | Structured *document* review (explicitly not code execution); verdict follows from its own issues, mirroring Red Team's rule |

**Orchestration**: `pm → architect → engineer` (one `asyncio.gather` call per component, `return_exceptions=True` so one component's failure doesn't abort the build) `→ qa` → deterministic `qa_gate` → **bounded revision** (`revise ⇄ qa`, `MAX_QA_ROUNDS=2` — i.e. exactly one revision attempt, same "total rounds" convention as `MAX_REFINEMENT_ROUNDS`) → `finish` (persists `BuildDossier`: `complete` or an honestly-surfaced `needs_revision`).

**Live-verified** (2026-07-06) against the real "TrustLayer SDK" opportunity: PM proposed 7 features, Architect designed 4 components (SDK Core Integration, Metrics Engine, GitHub Action Plugin, Evaluation Store), Engineer scaffolded all 4 (`main.py` ×2, `README.md`, `schema.sql` — the keyword heuristic chose correctly, including the README fallback for the GitHub Action plugin), QA **blocked** round 1 on 2 real critical issues (stub methods that don't call the real API), `revise` correctly re-ran only those 2 named components, QA **blocked again** on round 2 (1 remaining critical issue), and — with `MAX_QA_ROUNDS` exhausted — the build honestly landed on `needs_revision`, not a silently-accepted `complete`. This is the same "the bounded loop worked, this is a feature not a failure" story as venture pipeline's own 2 honest parks in Phase 1.5.

**Failure handling**: per-component containment inside Engineer's fan-out (mirrors `execute_venture`'s per-idea containment, one level deeper); the whole build is contained by `runner.execute_build`'s try/except (`build.status="failed"` + error event, never propagates).

---

## 7. LLMOps / AgentOps

- **Prompt management**: prompts are Python string constants co-located with the agent that uses them (e.g., `RESEARCH_SYSTEM_PROMPT`, `SCORE_PROMPT_TEMPLATE`, the inline prompts inside each `venture/agents.py` function). **No prompt versioning system** — this is a real gap for a "production-grade" claim; currently, prompt changes are just git history.
- **Observability**: `telemetry.configure_telemetry()` wires LangSmith (env-var based) and Pydantic Logfire (`logfire.span` around every agent call, `logfire.instrument_pydantic()`). **Verified live 2026-07-06**: `LANGSMITH_API_KEY`/`LOGFIRE_TOKEN` were supplied; a real discovery-pipeline run and a real build-squad run were both confirmed landing in LangSmith via its REST API (`/runs/query`, matching run IDs/timestamps/node names — `human_gate`, `qa`, `route_after_qa`, `mark_needs_revision`, etc.), and Logfire's `configure()` printed a real, working project URL (`https://logfire-us.pydantic.dev/dsharp/starter-project`) with no auth error. No longer a gap.
- **Logging**: every pipeline/venture/build node writes a `RunEvent` row (agent, event_type, message, duration_ms) — this is the AgentOps timeline. Now rendered in the UI too: `/console/runs/[id]` shows the full timeline for one run; `/console/opportunities/[id]` shows the parsed dossier plus any build scaffold.
- **Monitoring**: none beyond the above (no dashboards, no alerting).
- **Evaluation pipeline**: **two independent evals now, both live.** `p2pops-eval` (`evals/analyst_eval.py`) turns `Review.decision` (surfaced on `Idea.status`) into an agreement-rate + score-correlation report against the Analyst's shortlist — no `BRAINTRUST_API_KEY` exists, so this ships dependency-free rather than forcing an unavailable hosted tool (same judgment call as OKF, §12). Honest scope limit: only measures the Analyst's *precision*; recall is unmeasured since analyst-rejected ideas never reach a human today. **Promptfoo** (`promptfooconfig.yaml` + `evals/promptfoo_provider.py`, ADR-0008) is the second, newer eval: an `exec:` provider that calls the REAL `analyze_idea`/`validate_problem` functions (not copied prompt text) against 5 fixed scenarios, live-verified 5/5 against Groq. Deliberately NOT run on every CI push (real LLM cost) — a separate manual/weekly `promptfoo.yml` workflow; `ci.yml` only validates the config's schema for free.
- **Guardrails**: NeMo Guardrails input rail on every discovered idea before it reaches scoring (`guardrails.py`). No output rails yet.
- **Human-in-the-loop**: the email gate (ADR-0002), live-verified end to end.
- **Cost optimization**: `max_tokens` caps everywhere (learned the hard way — an uncapped default 64k-token request 402'd against a low-credit account); `MAX_RESEARCH_STEPS`, `MAX_SEARCH_RESULTS=6`, `MAX_ARTICLE_CHARS=1200` all exist specifically to bound spend/context-growth per run; sequential (not parallel) venture-pipeline execution per run is an explicit cost/concurrency control.
- **Cost tracking / FinOps** (new, Phase A, ADR-0009): `cost_tracking.record_usage` captures every structured-output call's token counts and an estimated USD cost (`pricing.py`, a dated list-price table; unknown models cost $0.00 rather than raising) into an `LlmCall` row — best-effort, wrapped so a tracking failure can never break the pipeline it's observing. Three call-site shapes feed it: `venture.agents._structured` (covers venture *and* build-squad, one seam), the Analyst's scorer, and the Research Agent's per-message ReAct capture. Exposed via `GET /api/v1/costs` and a console panel (spend/calls/tokens, broken down by agent and by model). **Live-verified**: a real discovery run recorded 6 calls / 5,965 tokens / ~$0.00077, rendered correctly in the deployed console.
- **Model routing**: `LLM_PROVIDER` env switch across Anthropic/OpenRouter/Groq, with per-tier (`default`/`builder`) model selection — this is LiteLLM's and the project's actual "swap providers via config" value proposition, demonstrated for real (all three providers have been live-called this session).
- **Hallucination mitigation**: evidence-grounding requirements baked into prompts (cite E-numbers, no fabricated TAM, no idea without a real `source_url`); clamping validators on numeric scores rather than trusting the model to respect a schema's stated range.

---

## 8. Infrastructure & Deployment

**Status: fully built and live-deployed as of Phase A (2026-07-07).** Every item below was previously "none" — this section is a complete rewrite, not an incremental update.

- **Public URLs (live now)**:
  - Web: **https://protopro.vercel.app** — Vercel project `asmq333/protopro`, deployed from `web/` via `vercel deploy --prod` (standalone Next.js output). `PROTOPRO_API_URL` is set as a Production env var pointing at the Render API.
  - API: **https://protopro-api.onrender.com** — Render web service `protopro-api`, provisioned from `render.yaml` (a Render Blueprint) via the dashboard's "New → Blueprint → connect repo" flow, building `Dockerfile` directly. Confirmed responding: `GET /api/v1/health` → `{"status":"ok","database":true}`.
  - **Verified wired together**, not just both independently up: the deployed console at `/console` renders "API connected" (not the seeded-fallback "API offline" state), meaning the Vercel-hosted frontend is successfully calling the Render-hosted API over the public internet.
- **Docker**: `Dockerfile` (API — multi-stage: `uv` builder → `python:3.13-slim` runtime, non-root user, `DATA_DIR=/app/data` baked in) and `web/Dockerfile` (Next.js `output: "standalone"`, multi-stage, non-root). Both build and run clean — verified via `docker compose up --build` locally (both containers reported `healthy`, web→api connectivity confirmed over the compose network). `docker-compose.yml` is the one-command local entrypoint; `docker-compose.dev.yml` is an override adding API hot-reload (bind-mounted `src/`, `uvicorn --reload`) — web dev stays native (`pnpm dev`) since containerized fast-refresh on Windows/macOS bind mounts is materially worse.
- **A real bug found by containerizing** (documented in ADR-0007, do not reintroduce): `db/engine.py` used to derive the SQLite directory from `database_url` via `url.rsplit("///", 1)`. On a POSIX absolute `data_dir` (e.g. `/app/data`, which produces a *four*-slash URL, `sqlite+aiosqlite:////app/data/protopro.db`), that rsplit strips the leading slash and yields a *relative* path — the API container crash-looped on first boot (`PermissionError: 'app'`). Windows drive-letter paths never triggered it, which is exactly why 48 previously-green tests missed it. Fixed by using `settings.data_dir` directly instead of re-parsing the URL.
- **Kubernetes** (`deploy/k8s/`, optional — not the primary deploy path, see ADR-0007 for why): a namespace, ConfigMap, Secret template (`secret.example.yaml`, real `secret.yaml` gitignored), an API Deployment+PVC+Service (**pinned to `replicas: 1`, `strategy: Recreate`** — SQLite is single-writer, so this is an honest architectural constraint encoded in the manifest, not an oversight), a web Deployment+Service+HorizontalPodAutoscaler (2-5 replicas, CPU-triggered — safe because the web tier is stateless by the Phase 2 seeded-fallback design), and an Ingress routing `/api`+`/r` to the API and `/` to web. Tied together with `kustomization.yaml`; rendered clean via `kubectl kustomize deploy/k8s`. **Not applied to a live cluster** — none was available on the development machine; this exists to demonstrate the orchestration pattern and to be genuinely usable the moment a cluster exists (`kubectl apply -k deploy/k8s` after creating the `protopro-secrets` Secret from `.env`).
- **CI/CD**: `.github/workflows/ci.yml` runs on every push — backend (ruff + pytest), web (eslint + `next build`), Docker builds of both images (with GitHub Actions layer caching), and a Promptfoo *config schema* validation step (free, no LLM calls). `.github/workflows/promptfoo.yml` is separate and deliberately NOT triggered by every push — `workflow_dispatch` (manual) + a weekly schedule, runs the real live-LLM eval suite, and skips gracefully with a `::notice::` if no `GROQ_API_KEY` secret is configured (same "degrade honestly, don't force an unavailable tool" pattern as the homegrown eval and the OKF write-up).
- **Deployment strategy** (ADR-0007, now executed, not just decided): web on Vercel (first-party Next.js hosting, zero containers to manage), API on Render (a single small container host with a persistent volume for SQLite) — deliberately NOT Kubernetes for the public demo; a single-operator portfolio project doesn't earn a managed cluster's cost/complexity, and the K8s manifests exist to demonstrate the pattern, not to run it. Render's Blueprint (`render.yaml`) is pinned to the `starter` plan with a 1GB disk mounted at `/app/data` — the plan can be downgraded to `free` (delete the `disk:` block) at the cost of the SQLite data resetting on every redeploy and the service sleeping after idle; this trade-off is documented directly in `render.yaml`'s header comment.
- **Secrets management**: `.env` (gitignored), `.env.example` as the template. A real bug was found and fixed here: blank values (`KEY=`) parsed as empty string, not `None`, silently defeating truthy checks — fixed with a `field_validator` (`config.py`, `_BLANKABLE_FIELDS`) that normalizes every optional secret field. In production, secrets live in the Render dashboard's env-var UI (`sync: false` fields in `render.yaml`) and Vercel's project env-var UI (`PROTOPRO_API_URL` set via `vercel env add`) — never in either platform's git-tracked config.
- **Environment variables**: fully enumerated in `.env.example` — provider keys, model overrides, HITL email config, API token, data directory. See §13.
- **Build process**: `uv sync` (Python), `pnpm install` (web) locally; `docker build` for both images in CI/deploy. Web additionally needs `output: "standalone"` in `next.config.ts` (added Phase A) for the Docker image's minimal runtime stage.
- **Testing process**: `uv run pytest` — 56 tests, all passing. Now actually enforced in CI (`ci.yml`, every push) — no longer "no CI exists."
- **Scalability considerations**: SQLite is still the datastore, and the constraint is now *encoded in the deployment topology itself* (API pinned to 1 replica everywhere — Compose, K8s, Render) rather than just noted in a doc. Postgres migration remains the unlock for horizontal API scaling (a connection-string change, schema is already ORM-defined); the web tier already scales freely today (Vercel is inherently multi-region/serverless; the K8s manifest's HPA demonstrates the same idea for a self-hosted cluster).

---

## 9. UI / UX Vision

- **Design philosophy**: "obsidian & ember" — a black stage with one glossy maroon signal color, explicitly designed to avoid the generic "AI startup template" look. Full rationale in ADR-0001.
- **Palette**: ink/mist/maroon token scales defined in `web/src/app/globals.css` (`--color-ink-950` through `--color-maroon-200`), plus `glass`, `ember-gloss`, and `grain` utility classes.
- **Typography**: Inter (UI), Instrument Serif italic (editorial/display moments — e.g., the word "Products" in the hero), JetBrains Mono (data/labels), all via `next/font`.
- **Dashboard vision**: the `/console` page is the *current* realization of the "recruiter-facing operations proof" idea — a module grid with live/wiring status per subsystem (Orchestration, Runs, Guardrails, Human gate, Tracing, Evaluations), a live run-store metrics strip (runs / ideas / approvals / dossiers, rendered force-dynamic with an explicit API connected/offline indicator), and "Recent runs"/"Recent opportunities" lists linking into two read-only deep-view pages: `/console/runs/[id]` (the full `RunEvent` timeline) and `/console/opportunities/[id]` (the parsed `OpportunityDossier` — vision, ranking, gates — plus any `BuildDossier` scaffold). **Still missing**: a per-agent cost view and a real visual graph-state representation (today's timeline is a linear list, not a graph) — that's the natural next UI milestone.
- **Components**: `Nav` (with the deliberately discreet Console entry, top-right), `Hero` (CSS-animated, live discovery ticker), `Showcase` (real pipeline-derived case cards), `Method` (5-stage agent production line), `PipelineStats`, `Footer`, `Reveal` (the scroll-triggered motion primitive — deliberately *not* used above the fold, per ADR-0003); the console's run/opportunity detail pages are plain server components, no client-side interactivity needed for a read-only view.
- **Animations**: CSS-only for anything above the fold (`animate-rise` keyframes with staggered `animation-delay`) — a real bug (hero content invisible until JS hydration) was found and fixed by this exact rule. Below the fold, `Reveal` uses the `motion` library's `whileInView`.
- **User flow**: land on `/` → read the hero/ticker → scroll through Showcase/Method/Stats → optionally click the quiet Console pill for the engineering view. No authenticated user flow exists (no login, no accounts) — the whole site is public-read, single-operator-controlled.

---

## 10. Development Decision Log

(Condensed; full reasoning lives in `docs/adr/000N-*.md` and `implementation-notes.md`'s phase log.)

| Decision | Date | Reasoning | Alternatives considered | Trade-off accepted |
|---|---|---|---|---|
| Reverse Streamlit → custom Next.js frontend | 2026-07-05 | Premium design bar unreachable with Streamlit's rerun model | Streamlit (rejected), Vite+React SPA | Two toolchains (uv + pnpm) in one repo |
| HITL over email, not a web review UI | 2026-07-05 | Founder explicitly wanted no public review workflow | In-app review dashboard | Review action links are still HTTP endpoints (token-gated, unlisted — not a contradiction, a clarified scope) |
| Above-the-fold content must be CSS-only animated | 2026-07-05 | JS-hydration-gated hero content is bad for LCP and was observed broken in headless-browser testing | Keep JS-only `Reveal` everywhere | One extra utility (`animate-rise`) and a rule to remember |
| Venture pipeline: code decides, LLMs propose | 2026-07-06 | Explainability/reproducibility requirement; avoids "trust the model" ranking | Let an LLM rank/gate directly | More code (scoring.py) but fully unit-testable and deterministic |
| Curated principle library over "just ask the LLM for ideas" | 2026-07-06 | Makes "learn from successful founders" auditable and specific, not vibes | Free-form brainstorming prompt | Library is currently fixed at 8 entries, hand-curated (a maintenance surface) |
| Bounded refinement loop (max 2 rounds), park don't loop forever | 2026-07-06 | A real venture studio kills ideas; infinite refinement isn't honest | Unbounded retry until clean | Some genuinely fixable ideas might get parked at round 2 when round 3 would've worked — acceptable, tunable constant |
| Groq as a third provider, `llama-4-scout-17b-16e-instruct` as default | 2026-07-06 | Anthropic and OpenRouter both ran out of credit; Groq's `gpt-oss-20b` hit an 8k TPM ceiling live; measured actual per-model limits on the account before choosing (30k TPM, verified tool-calling + structured output) | Wait for OpenRouter top-up, use gpt-oss-20b with more retries | Groq-specific model IDs now baked into defaults; provider-agnostic design still holds (config-only switch) |
| Single retry seam (`resilience.with_retry`), `max_retries=0` on all chat clients | 2026-07-06 | Two uncoordinated retry layers (SDK's own + ours) were observed stacking unpredictable multi-minute waits live | Rely on each SDK's built-in retry | One more module to maintain, but now the *only* place retry policy is decided |
| Status-code-first error classification, with two named exceptions (413 wording collision, `tool_use_failed`/`json_validate_failed`) | 2026-07-06 | Both exceptions were *observed live*, not theorized — text-only classification would have gotten both wrong in opposite directions | Match on error message text alone | A slightly more complex classifier, fully unit-tested (9 tests) |
| `p2pops` package name kept despite `ProToPro` brand | 2026-07-05 | Renaming is pure churn, no user-visible value pre-publish | Rename to `protopro` | Minor internal/external naming mismatch, documented |
| Build-squad trigger is CLI/protected-POST only, no public UI button | 2026-07-06 | `/console` is unauthenticated and labeled "Internal · read-only"; a public button would let any visitor spend LLM budget, contradicting the HITL-first philosophy | A "scaffold this" button on the opportunity page | One more manual step for the operator (running a CLI command) |
| Build-squad fan-out via `asyncio.gather`, not LangGraph `Send` | 2026-07-06 | Venture's own 4-way fan-out already uses fixed named nodes, not `Send`; introducing `Send` would add a second orchestration primitive (plus `Annotated` reducer fields) for a bounded, non-recursive fan-out that doesn't need it | LangGraph `Send`/map-reduce | None significant — `return_exceptions=True` still gives per-component failure containment |
| `MAX_QA_ROUNDS=2` (not 1), same "total rounds" convention as `MAX_REFINEMENT_ROUNDS` | 2026-07-06 | Setting it to 1 (following "one revision round" literally) was tried first and caught by the offline test suite as a real off-by-one — `round_index < MAX` never allows a revision at `MAX=1` | Change the comparison operator instead of the constant | Keeps `route_after_qa` identical in shape to venture's `route_after_stress`, only the constant differs |
| Deployment: Vercel (web) + Render (API), not Kubernetes | 2026-07-07 | A single-operator portfolio project doesn't earn a managed cluster's cost/complexity; Vercel is first-party Next.js hosting; Render deploys straight from `render.yaml` with zero manual container ops | Self-hosted K8s (kind/a cloud cluster) for the public demo | The K8s manifests still exist (`deploy/k8s/`) to demonstrate the pattern, just aren't the live deploy target |
| API pinned to 1 replica everywhere (Compose, K8s, Render) | 2026-07-07 | SQLite is single-writer; encoding this as `strategy: Recreate` + a single instance in every deploy target is honest about the real constraint rather than letting an autoscaler silently corrupt data | Multi-replica with a shared volume | No horizontal API scaling until the Postgres migration lands |
| Promptfoo provider calls the real agent functions, not copied prompts | 2026-07-07 | A regression suite testing a duplicated prompt string only catches drift between the copy and the original, never a real behavioral regression | Hand-write prompts inline in the promptfoo config | The `exec:` provider protocol needed reverse-engineering from promptfoo's own source (verified, not guessed) since the "prompt" concept doesn't map cleanly onto "call a real function" |
| Promptfoo runs on a separate manual/weekly workflow, not every push | 2026-07-07 | Real LLM calls cost real money; `ci.yml`'s promptfoo step only validates config schema (free) | Run the full eval suite on every push | A prompt regression could theoretically sit undetected for up to a week between scheduled runs, or until manually triggered |
| LLM cost ledger is global, not run-scoped | 2026-07-07 | Keeps the schema and every call site simple for a single-operator project; a `run_id` FK is a straightforward additive migration if per-run cost ever becomes a real need | Add `run_id`/`opportunity_id` FKs to `LlmCall` now | Console's cost panel shows aggregate spend, not "this run cost $X" — acceptable at current scale |
| `include_raw=True` re-raises `parsing_error` explicitly at both cost-tracking call sites | 2026-07-07 | `with_structured_output(..., include_raw=True)` (needed to capture token usage) changes LangChain's contract from "raise on malformed output" to "return a `parsing_error` field instead" — left unhandled, this would have silently defeated ADR-0005's retry-on-`tool_use_failed` logic, since the exception `with_retry` classifies on would simply never be raised | Skip `include_raw` and estimate tokens from prompt/completion length instead | One more explicit check at each call site, but real usage numbers instead of estimates |
| Approval auto-chains venture → build → publish (supersedes ADR-0006's manual-only trigger) | 2026-07-11 | The human approval IS the spend authorization; a second manual step between "approved" and "building" was a silent stall, not a safety layer. Still no public build trigger anywhere | Keep manual CLI-only builds | See ADR-0010 |
| Build target = working client-side web MVP (static HTML/CSS/JS + localStorage) | 2026-07-11 | The showcase can only honestly link to something that works when opened; this is the largest unit a small model ships reliably | Scaffold-with-TODOs (old), full-stack repo generation (unreliable) | Server-side products out of v1 scope by design (ADR-0010) |
| Engineers sequential with sibling files in context, not parallel fan-out | 2026-07-11 | First live MVP build failed QA on cross-file drift (JS referencing ids the HTML never defined) — interlocking files can't be written blind | Keep `asyncio.gather` fan-out | ~10s more wall time per build; linear in component count (ADR-0010) |
| Deterministic asset linker (`scoring.link_assets`) guarantees HTML references every built CSS/JS | 2026-07-11 | Small models forget/misorder `<script>`/`<link>` tags — observed as a QA-blocking critical two builds running; tag insertion is a code decision, not an LLM one | Prompt harder and hope | One more deterministic post-step; runs before QA so reviews see the real product |
| PTP numbers assigned at shortlist time in `save_idea`'s transaction; seeds hold 1–3 | 2026-07-11 | Validated problems get a public identity; rejected/duplicate noise never burns a number; DB numbering starts at 4 so it can never collide with the seeded cards | Number at discovery; renumber per page render (old showcase behavior) | Backfilled 12 historical validated ideas (PTP-005…016) in discovered-at order |
| Public search endpoint is open; spend controls are layered, not auth-gated | 2026-07-11 | "Any visitor can point the pipeline at a topic" is the feature; per-client + global caps, keyword dedupe, cost ceiling and a keyword-tuned rail all run before any token is spent, and the human gate still guards every build | Require login/token for search | A determined botnet could exhaust the daily caps (they're cheap by design); see ADR-0010 |
| Engineer/QA/Architect moved off the 8k-TPM builder tier | 2026-07-11 | Whole product files + grown instructions don't fit gpt-oss-120b's measured ceiling (reasoning tokens count against it); observed as permanent 413/4-strike failures, not transient 429s | Shrink prompts to fit | PM keeps the builder tier; revisit if account limits change |

---

## 11. Roadmap

**Everything in the original "Immediate next tasks"/"Short-term milestones" from the previous handoff is now done**: Promptfoo, CI/CD, Docker Compose, and real deployment (Vercel + Render, live) all shipped and live-verified in Phase A (2026-07-07). What's left is genuinely optional polish, not core capability.

### Immediate next tasks (next session should start here)
1. **Get real email delivery live**: the user explicitly wants review-request and product-ready emails in their inbox. Everything is wired (`notify.send_review_request` + the new `send_product_ready`); the ONLY missing piece is a `RESEND_API_KEY` (free tier exists) set locally and in the Render dashboard alongside `REVIEW_EMAIL_TO`. Until then both emails log to the server console.
2. **Confirm the production data story**: the Render DB was observed EMPTY on 2026-07-11 despite a live pipeline run having executed against it on 2026-07-07 — i.e., the data did NOT survive (free plan or disk misconfig). Decide: pay for the starter disk, or accept reset-on-redeploy and let the web tier's seeded fallback carry the showcase (that fallback now includes the shipped product story).
3. **Prod full-loop run**: trigger a search on the live site, approve it from the live console queue (needs the `API_TOKEN` from the Render dashboard as the operator key), and let it auto-build+publish — requires `VERCEL_TOKEN` set in Render's env for the publish stage.
4. Grow the eval dataset and revisit `p2pops-eval`'s recall gap (unchanged from last session).
5. Raise the MVP build pass-rate (QA still blocks honestly on model quality; see §15's build-iteration story).

### Short-term milestones
- Wire `p2pops-eval`'s report to Braintrust's hosted `Eval(...)` if/when a `BRAINTRUST_API_KEY` becomes available — the module is already structured for this.
- Extend the Promptfoo suite to cover Architect/Red Team/build-squad scenarios (currently only Analyst + Validator) — the MVP-build agents especially, given this session's live iteration on them.
- Render auto-deploys on push to `master` (confirmed live 2026-07-11: the prod API picked up version 1.1 without dashboard action). Vercel web deploys are still manual `vercel deploy --prod`.
- Semantic (Chroma) keyword dedupe for public search, beyond exact-normalized match.

### Medium-term milestones
- Postgres migration (swap the one `database_url` connection string; schema is already ORM-defined, no rewrite needed) — this is what unlocks horizontal API scaling, since every deploy target (Compose, K8s, Render) is currently pinned to 1 API replica specifically because SQLite is single-writer.
- Console per-agent cost view refinement: currently aggregate/global (ADR-0009); a run-scoped cost view is a straightforward additive `run_id` FK if it becomes a real need.
- A real graph-state visualization in the console (beyond the linear event timeline).

### Long-term vision
- Cross-run learning: venture agents drawing on a vector store of past `OpportunityDossier`s (RAG over the project's own history), not just per-run evidence.
- Multi-topic/scheduled discovery runs (currently always manually triggered via POST).
- Reddit as a second discovery source (PRAW, OAuth) — deferred, not abandoned.
- Raise `build/scoring.MAX_QA_ROUNDS` past 2 only after re-deriving the fan-out cost math documented next to the constant.

### Stretch goals
- OKF-formatted principle library (see §12 below) — small, well-justified, genuinely current (June 2026 spec).
- Apply `deploy/k8s/` to a real cluster (a local `kind`/`minikube`, or a cloud one) — currently only kustomize-rendered and validated, never applied, since no cluster was available on the dev machine.

---

## 12. Technical Debt

### Known issues
- **`data_dir="data"` is still CWD-relative for local/native runs** — starting `p2pops-api` with `uv run` from any directory other than the repo root silently creates a fresh, empty database there. Unchanged by Phase A. **Not an issue in any deployed/containerized context** (Docker, Compose, K8s, Render) — all of them set `DATA_DIR` to an absolute path explicitly, and Phase A additionally fixed a related-but-distinct bug (below) that only manifested with an absolute path.
- **Fixed this session**: `db/engine.py` used to derive the SQLite directory via `url.rsplit("///", 1)` on `database_url`. This is correct for a relative `data_dir` (three-slash URL) but silently wrong for a POSIX *absolute* `data_dir` (four-slash URL: `sqlite+aiosqlite:////app/data/...`) — the rsplit strips the leading slash and produces a relative path, which crash-looped the Docker container on first boot. Fixed by using `settings.data_dir` directly. Windows paths never hit this, which is why it survived 48 previously-green tests; **if this logic is ever touched again, test it against a POSIX absolute path, not just the Windows dev machine's paths.**
- **`SHORTLIST_THRESHOLD=50`, `MAX_REFINEMENT_ROUNDS=2`, `MAX_QA_ROUNDS=2`** are hardcoded module constants, not configurable — fine for now, explicitly logged as "revisit once there's a dashboard to tune them from" (Analyst) / "a real venture studio kills ideas" (venture, design stance) / "fan-out multiplies cost per round, don't raise casually" (build, cost math documented next to the constant).
- **Build-squad scaffolds are DB-only** — `scaffold_files` content is real and inspectable via the console, but nothing writes it to an actual directory on disk yet; a human wanting to actually start from the scaffold has to copy-paste from the dossier viewer.
- **`.gitignore` had an unanchored `build/` rule** (paired with `dist/`, meant for Python packaging's top-level build-artifact directory) that silently excluded the entire new `src/p2pops/build/` package from git — caught before committing by `git status` showing the new backend files but not the package itself. Fixed by anchoring both to the repo root (`/build/`, `/dist/`). Worth remembering if any future top-level-sounding directory name is added under `src/`.

### New this session (2026-07-11)
- **The production Render DB was found EMPTY** (`runs: 0`) despite the 2026-07-07 live verification having executed a pipeline run against it — production data does not currently survive (free-tier behavior or disk misconfig). The public site's seeded fallback carries the showcase either way; §11 task 2 is the decision point.
- **Emails still console-logged**: `RESEND_API_KEY` remains unset (locally and presumably on Render). The user has explicitly asked for real review + product-ready emails — this is now the top of §11.
- **A pre-existing "unique" gap**: `ideas.ptp_number` gets a UNIQUE index only on fresh databases (SQLite `ALTER TABLE ADD COLUMN` can't add constraints); migrated DBs rely on the single-writer assignment logic. Postgres migration should add the real constraint.
- **QA truncation**: QA reviews files capped at 9000 chars each; a product whose HTML legitimately exceeds that re-opens the "unverifiable undefined-id finding" class of issue.

### Temporary implementations (explicitly logged deviations)
- `Base.metadata.create_all` instead of Alembic migrations (ADR/phase-log-logged deviation from the original "modular monolith" plan) — fine pre-1.0 with a single developer and SQLite; must become Alembic before any real schema change lands on a populated Postgres database. **Now higher-stakes than before**: the production Render deployment runs this same `create_all` on every boot against real (if small) persisted data.
- Email HITL's Console adapter (prints instead of sending) is what every live test so far has actually exercised — Resend has never been used in anger (no `RESEND_API_KEY` supplied yet). This is now also true in production: unless `RESEND_API_KEY`/`REVIEW_EMAIL_TO` were set in the Render dashboard, review emails from the live deployment log to Render's console instead of sending.
- Render's `starter` plan (as pinned in `render.yaml`) costs money; if the actual dashboard deploy used `free` instead, the SQLite data resets on every redeploy and the service sleeps after idle — verify which plan is live and update the deploy docs/resume claims accordingly (see §11's first immediate task).

### Performance improvements
- Venture pipeline runs one approved idea at a time per run (deliberate cost control, not a bug) — parallelizing across ideas (not within one idea's stress/refine loop, which should stay sequential) is a reasonable future lever if run volume grows.

### Refactoring opportunities
- `llm.py`'s `complete()` has no retry wrapping — single caller (bootstrap check), low priority, but should move onto `resilience.with_retry` if it ever gets a second caller.
- The principle library (`venture/principles.py`) is a hardcoded Python list — fine at 8 entries, would benefit from externalization (see OKF discussion, §12-OKF below) if it grows or needs non-engineer editing.

### Security improvements
- **No authentication beyond an optional single bearer token on mutating API endpoints (`API_TOKEN`) — this gap is now materially more important than before**, since `/api/v1/runs` and `/api/v1/builds` on the deployed Render API have a real public URL and, if `API_TOKEN` isn't set there, are wide open to anyone who finds it (each POST spends real LLM budget). **Verify `API_TOKEN` is actually set in the Render dashboard** — `render.yaml` has it as `generateValue: true` so Render should have generated one automatically, but this should be confirmed, not assumed.
- Review action tokens are single-use and expiring (`review_token_ttl_hours`) — good; but the email itself (Console adapter) currently just logs to stdout, meaning anyone with Render log/dashboard access effectively has the approve/reject links. Low risk (single-operator project) but worth knowing before treating this as a security boundary.
- CORS on the API (`api/app.py`) is currently allow-listed to `localhost:3000`/`127.0.0.1:3000` only — **the deployed Vercel frontend calls the API server-side** (Next.js server component → API, never browser → API directly), so this hasn't caused an issue live, but if any client-side fetch to the API is ever added, the CORS origins list needs `https://protopro.vercel.app` added or it will silently fail in the browser only.

### On Google's Open Knowledge Format (OKF) — evaluated, not blindly adopted

**What it actually is** (verified via web search, since it launched June 12, 2026 — after this assistant's training cutoff, and was *not* assumed or guessed): OKF is a Google Cloud specification (v0.1, still evolving) for representing curated organizational knowledge — a directory of markdown files with YAML frontmatter, following shared conventions — so that knowledge written by one producer can be consumed by AI agents from different vendors without custom translation. It formalizes the "LLM-wiki" pattern (similar in spirit to `llms.txt`/`CLAUDE.md`-style context files, but standardized and directory-shaped).

**Where it does NOT fit this project** (and would be technology-for-its-own-sake if forced in):
- It is not an orchestration framework — does not touch LangGraph.
- It is not a database format — `Run`/`Idea`/`Opportunity` are transactional relational records, not curated reference knowledge; OKF-ifying them would be a category error.
- It is not an eval or observability framework — irrelevant to the Braintrust/Promptfoo gap or the (now-closed) LangSmith/Logfire verification gap.

**Where it does genuinely fit**: `venture/principles.py` — the curated library of founder/company patterns (Airbnb, Stripe, Canva, Notion, Duolingo, Figma, Slack, Shopify, Vercel) that the Architect agent cites and the Red Team attacks by documented failure mode — **is** exactly the kind of curated, human-authored, agent-consumed knowledge OKF exists to standardize. Recommendation: **a small, optional future refactor**, not urgent — externalize this library as an OKF-formatted `knowledge/principles/` directory (one markdown file per principle, YAML frontmatter for `key`/`company`/`when_applicable`/`failure_mode`, prose body for the principle itself), loaded at runtime instead of hardcoded as a Python list of Pydantic objects. Benefits: non-engineers could edit/extend the principle library without touching Python; demonstrates deliberate, judgment-based adoption of a brand-new (weeks-old at time of writing) vendor-neutral standard exactly where it fits — which reads to a hiring manager as "tracks the ecosystem and applies judgment," not "chases buzzwords." **Not done yet** — logged here as a well-justified stretch goal (§11), explicitly not force-fit elsewhere.

---

## 13. Environment & Setup

### Installation
```bash
# Backend
cd p2pagent
uv sync

# Frontend
cd web
pnpm install
```

### Environment variables (`.env`, see `.env.example` for the template)
```
ENVIRONMENT=development

# --- LLM access, routed through LiteLLM / native LangChain clients ---
LLM_PROVIDER=groq              # anthropic | openrouter | groq
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=
GROQ_API_KEY=                  # currently the only funded provider

# --- Observability (verified live 2026-07-06 via LangSmith REST API + Logfire auth) ---
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=p2pops
LOGFIRE_TOKEN=

# --- Discovery sources ---
REDDIT_CLIENT_ID=              # unused -- Reddit source not implemented
REDDIT_CLIENT_SECRET=

# --- HITL orchestration (human gate, ADR-0002) ---
REVIEW_INTERVAL_DAYS=10
REVIEW_EMAIL_TO=               # blank = console adapter (logs instead of sending)
RESEND_API_KEY=                # blank = console adapter
APP_BASE_URL=http://localhost:8000

# --- API ---
API_TOKEN=                     # blank = open (no auth) -- fine for local/demo only

# --- Product publishing (build-squad publish stage, ADR-0010) ---
VERCEL_TOKEN=                  # blank = publish stage skips honestly (no Live claim)
VERCEL_TEAM_ID=                # optional; defaults to the token's default team

# --- Public keyword search spend controls (ADR-0010) ---
SEARCH_REQUESTS_PER_HOUR_PER_CLIENT=3
SEARCH_RUNS_PER_DAY=8
SEARCH_DEDUPE_HOURS=24
DAILY_COST_CEILING_USD=1.0     # public search stops starting runs above this; console shows an alert
```
Note: **blank values are safe** — `config.py`'s `_blank_to_none` validator normalizes `KEY=` to `None` for every optional field, fixing a real bug where this used to silently break auth (ADR-0005).

### Commands
```bash
# Backend
uv run pytest                        # 56 tests
uv run ruff check src tests          # lint (CI's exact command)
uv run p2pops                        # bootstrap check (one LLM call)
uv run p2pops-research "<topic>"     # Research Agent standalone
uv run p2pops-pipeline "<topic>"     # full discovery pipeline, one CLI run
uv run p2pops-api                    # FastAPI server, http://localhost:8000
uv run p2pops-mcp-server             # MCP server standalone (stdio)
uv run p2pops-eval                   # Analyst-vs-human agreement report
uv run p2pops-build <opportunity_id> # scaffold one complete opportunity (build-squad)
uv run p2pops-promptfoo-provider ... # promptfoo's exec: provider entrypoint (not called directly)

# Frontend
cd web && pnpm dev                   # http://localhost:3000
cd web && pnpm build && pnpm start   # production build
cd web && pnpm lint

# Docker (one command, both tiers)
docker compose up --build            # api: http://localhost:8000, web: http://localhost:3000
API_PORT=8010 WEB_PORT=3010 docker compose up --build   # if default ports are already taken locally
docker compose -f docker-compose.yml -f docker-compose.dev.yml up   # API hot-reload for dev

# Kubernetes (manifests exist; no cluster was available to apply against locally)
kubectl kustomize deploy/k8s                                          # render, sanity-check
kubectl apply -f deploy/k8s/namespace.yaml
kubectl -n protopro create secret generic protopro-secrets --from-env-file=.env
kubectl apply -k deploy/k8s

# Promptfoo (costs real LLM tokens — see ADR-0008 before running casually)
npx promptfoo@latest eval -c promptfooconfig.yaml --no-cache
```

### Deployment (live)
- **Web**: Vercel project `asmq333/protopro`. Redeploy after a `web/` change: `cd web && npx vercel@latest deploy --prod --scope asmq333` (needs a Vercel token — see `vercel login` or `vercel env` docs; none is stored in this repo). Env vars are managed in the Vercel dashboard / via `vercel env add` — currently just `PROTOPRO_API_URL=https://protopro-api.onrender.com`.
- **API**: Render service `protopro-api`, auto-builds from `render.yaml` whenever `master` is pushed (Render's GitHub integration watches the connected repo — **verify in the Render dashboard whether auto-deploy-on-push is actually enabled**; if not, redeploys must be triggered manually from the dashboard). Secrets (`GROQ_API_KEY`, etc.) are set directly in the Render dashboard's environment tab, never committed.
- **Full 3-tier deploy guide** (Compose / K8s / managed PaaS, with the reasoning for choosing PaaS as primary): `deploy/README.md`.

### Troubleshooting (real incidents encountered, see the referenced ADR for full detail)
- **"content: minimum number of items is 1" from Groq**: a tool returned empty content — already fixed at the source (`tools/web.py`, `mcp/server.py` never return bare `""`/`[]`), but if a *new* tool is added, apply the same rule.
- **API requests all silently 401 despite no token configured**: check `.env` doesn't have a genuinely non-blank-looking `API_TOKEN=` value with hidden whitespace; the blank-normalization only strips fully-blank strings.
- **A run fails immediately with "research failed after 1 attempt(s)"**: check the underlying error in the API server's log — status 4xx-other-than-429 and `GraphRecursionError` are deliberately not retried; this is very likely a genuine, reproducible problem, not a fluke.
- **A run hangs at `status: running` for a long time then fails with repeated "hit a rate limit" warnings**: the configured provider/model's TPM ceiling is too tight for the workload — check `docs/adr/0005-*.md`'s measured-limits table before assuming code is broken.
- **A Docker container crash-loops immediately with a `PermissionError` on `/app` or similar**: this is the exact `data_dir` URL-parsing bug fixed in `db/engine.py` this phase (ADR-0007) — if it recurs, something re-introduced `url.rsplit("///", ...)`-style parsing instead of using `settings.data_dir` directly.
- **`docker compose up` fails with "port is already allocated"**: something else on the machine already holds 8000/3000 (observed live: an unrelated `wc26-mlops` stack). Use `API_PORT=`/`WEB_PORT=` overrides rather than stopping the other stack.
- **`npx promptfoo`/`npx vercel` fails with `npm error code ECOMPROMISED` / "Lock compromised"**: a corrupted local npm cache (observed live on this Windows machine, unrelated to the project). Fix: `npm cache clean --force`, or bypass entirely with `npm_config_cache=/some/fresh/dir npx ...`.

---

## 14. Important Files

| File | Purpose | Why it exists | Key interactions |
|---|---|---|---|
| `src/p2pops/config.py` | All settings, env-driven | Single source of config truth; blank-string-safety validator lives here | Imported by nearly everything |
| `src/p2pops/chat_model.py` | Provider-agnostic chat model factory | Lets agent code not care which of 3 providers is active | Used by both agents' modules and all venture agents |
| `src/p2pops/resilience.py` | Rate-limit-aware retry | The single retry policy authority, born from 5 real live incidents | Used by `llm.py`, both discovery agents, all venture agents |
| `src/p2pops/graph.py` | Discovery pipeline StateGraph | Orchestrates research→analyst→human gate | Compiled + checkpointed in `runner.py` |
| `src/p2pops/venture/graph.py` | Venture opportunity StateGraph | Orchestrates evidence→analysis→gates→stress/refine→vision | Invoked per-approved-idea by `runner.execute_venture` |
| `src/p2pops/venture/scoring.py` | Deterministic ranking + gates | The "code decides, LLM proposes" architectural anchor | Consumed by `venture/graph.py` |
| `src/p2pops/venture/principles.py` | Curated founder-pattern library | Grounds the Architect agent's proposals in named, arguable precedent | Consumed by `venture/agents.generate_directions` |
| `src/p2pops/build/graph.py` | Build-squad StateGraph | Orchestrates pm→architect→engineer(fan-out)→qa gate→bounded revise | Invoked manually by `runner.execute_build`/`start_build`, ADR-0006 |
| `src/p2pops/build/scoring.py` | Deterministic QA gate + scaffold targeting | The build-squad half of "code decides, LLM proposes" — path/language are never the LLM's choice | Consumed by `build/graph.py` |
| `src/p2pops/evals/analyst_eval.py` | Analyst-vs-human agreement report | The first eval, dependency-free (no Braintrust key) | `p2pops-eval` CLI |
| `src/p2pops/evals/promptfoo_provider.py` | Promptfoo `exec:` provider | Dispatches to the REAL agent functions (ADR-0008), not copied prompts | Invoked by `promptfooconfig.yaml`'s `exec:` provider |
| `src/p2pops/cost_tracking.py` | LLM usage capture (best-effort) | The single seam every call site feeds; failures never break the pipeline (ADR-0009) | Called from `venture/agents._structured`, `agents/analyst.py`, `agents/research.py` |
| `src/p2pops/pricing.py` | USD/token rate table + cost estimation | Unknown model → $0.00, never raises — pricing can't be allowed to break agent execution | Consumed by `cost_tracking.record_usage` |
| `src/p2pops/runner.py` | Run lifecycle, owns the checkpointer | The only place that starts/resumes/executes runs, ventures, and builds | Called by `api/app.py`, `pipeline.py`, `build_cli.py` |
| `src/p2pops/db/repository.py` | All SQL | Single place that owns data-access semantics | Used by `runner.py`, `graph.py`, `venture/graph.py`, `build/graph.py`, `api/app.py`, `cost_tracking.py` |
| `src/p2pops/notify.py` | Email HITL delivery + product-ready notification | Implements ADR-0002; `send_product_ready` closes the loop's email story | Called by `graph.request_review_node` and `build/graph.publish_node` |
| `src/p2pops/publish.py` | Product packaging + Vercel deploy + smoke check | The Publish stage — deterministic code, honest failure modes (ADR-0010) | Called by `build/graph.publish_node`; needs `VERCEL_TOKEN` |
| `src/p2pops/tools/websearch.py` | Keyless general web search (DuckDuckGo HTML) | Broadens Research beyond HN without a paid search API | Exposed as the `search_web` MCP tool in `mcp/server.py` |
| `src/p2pops/mcp/server.py` | MCP tool server | Makes Research Agent's tools a real, portable MCP service | Connected to by `agents/research.py` via `langchain-mcp-adapters` |
| `Dockerfile` / `web/Dockerfile` | Multi-stage production images | ADR-0007; the actual images running on Render/behind Vercel-adjacent infra | `docker-compose.yml`, `render.yaml`'s `dockerfilePath` |
| `docker-compose.yml` / `.dev.yml` | One-command local startup + hot-reload override | Verified live: both containers healthy, web→api over the compose network | `deploy/README.md` |
| `deploy/k8s/*.yaml` + `kustomization.yaml` | Kubernetes manifests | Demonstrates the orchestration pattern (1-replica API, HPA'd web) even without a live cluster | `kubectl apply -k deploy/k8s` |
| `render.yaml` | Render Blueprint | The API's actual deploy config — read by Render's dashboard "New → Blueprint" flow | Drives `https://protopro-api.onrender.com` |
| `.github/workflows/ci.yml` | Push-triggered CI | Lint/test/build/docker-build/promptfoo-schema, zero LLM cost | Runs on every push to the GitHub repo |
| `.github/workflows/promptfoo.yml` | Live prompt-regression eval | Manual + weekly, real LLM calls, skips gracefully without a key | Needs `GROQ_API_KEY` configured as a GitHub Actions secret to actually run (unverified whether it is) |
| `promptfooconfig.yaml` | Promptfoo scenario suite | 5 scenarios, live-verified 5/5 against Groq | Read by both `promptfoo eval` locally and `promptfoo.yml` in CI |
| `web/src/lib/api.ts` | Server-side client for `/api/v1` | Feeds live pipeline data to the site with timeout + seeded-fallback semantics | Used by hero, showcase, pipeline-stats, console, cost panel, deep views, story pages, and the route-handler proxies |
| `web/src/components/search.tsx` | Public keyword-search section (client) | Feature 2's visitor entry point; polls run phase after submit | POSTs to `/api/search` (route-handler proxy) |
| `web/src/components/approval-queue.tsx` | In-console approval queue (client) | One-click approve/reject without depending on an inbox; operator key in sessionStorage only | `/api/console/reviews*` proxies → operator-protected API endpoints |
| `web/src/components/live-timeline.tsx` | SSE live tail of a run's events (client) | Makes an in-flight run watchable in real time | `/api/console/runs/[id]/stream` SSE passthrough |
| `web/src/app/showcase/[ptp]/page.tsx` | Permanent problem-to-product story page | Every PTP item is a durable case study, not just a card | `GET /api/v1/showcase/{ptp}` with `seed-story.ts` fallback |
| `web/src/app/api/**/route.ts` | Route-handler proxies (search, queue, SSE) | Browser never talks to the API host directly — CORS stays untouched, caller IP forwarded for rate limits | All client components above |
| `web/src/app/console/opportunities/[id]/page.tsx` | Opportunity + build dossier viewer | Read-only recruiter-facing view of the full venture + build-squad output | Reads `getOpportunity`/`getBuild` |
| `web/src/app/console/runs/[id]/page.tsx` | Run event timeline viewer | Renders the AgentOps `RunEvent` timeline the console previously only linked to via raw API | Reads `getRun` |
| `web/next.config.ts` | `output: "standalone"` | Required for the Docker image's minimal runtime stage (added Phase A) | `web/Dockerfile`'s runtime stage copies `.next/standalone` |
| `web/src/app/globals.css` | Design system tokens | The entire "obsidian & ember" visual identity | Used by every component |
| `docs/adr/*.md` | Architecture Decision Records | The actual engineering reasoning, not just outcomes | Referenced throughout this document |
| `implementation-notes.md` | Chronological phase log | Session-by-session build history, kept during development | Predecessor/complement to this file |
| `PROJECT_BRAIN.md` (this file) | Single source of truth | Enables a fresh session to continue with zero context loss | — |

---

## 15. Session Handoff — READ THIS FIRST

### What was completed in the most recent session (2026-07-11, Phase B: the closed loop, public search, and the FIRST SHIPPED PRODUCT)

**The headline: the full Discover → Validate → Approve → Build → Publish loop now runs end to end, and the first product is live: `https://ptp-011-trustlayer-sdk.vercel.app` (PTP-011, "TrustLayer SDK" — a working client-side trust-score evaluator, built entirely by the build squad, QA-passed, deployed and smoke-checked by the pipeline itself). Its showcase card and permanent story page are live on `https://protopro.vercel.app` / `/showcase/ptp-011`.** ADR-0010 documents the architecture decisions; implementation-notes.md has the phase entry.

#### Fully shipped and verified this session
1. **Closed loop**: human approval auto-chains venture → build squad → publish (`runner.resume_run`). Verified live: a keyword-search-discovered idea (PTP-004) was approved, ran venture, and was honestly *parked* by the stress gate; the already-approved TrustLayer opportunity (PTP-011) went build → QA pass → Vercel deploy → smoke check → `deploy_url` persisted → product-ready notification sent (console adapter).
2. **Build squad ships working MVPs** (client-side web apps). Getting there took TEN live build iterations, each fixing one observed failure mode — the full list is in implementation-notes.md's Phase B entry and ADR-0010; the headline fixes: sequential engineers with sibling files in context, raw-text `_completion` seam for code files, code-owned architecture shape (`consolidate_components`, `ensure_browser_components`, `link_assets`), a deterministic DOM-id reference audit that QA must not contradict (`undefined_dom_ids`), a flattened `ArchitectureSpec` (strict-schema mode), and a narrow critical-severity rubric for QA.
3. **Public keyword search**, live on the homepage and in production: `POST /api/v1/search` (guardrailed, rate-limited per client + per day, keyword-deduped, cost-ceilinged, audited in `search_requests`). Verified live locally (multiple full runs: discovery → shortlist → gate) and in production (run `fb569f7e…`, keyword "AI agent observability", source-tagged, awaiting review as designed).
4. **PTP numbering** (`ideas.ptp_number`, shortlist-time assignment, seeds hold 1–3, DB starts at 4) + 12 backfilled historical validated ideas (PTP-005…016). Showcase lifecycle (validated → building → live) served by `/api/v1/showcase*`; declined ideas leave the public showcase.
5. **Console real data**: in-console approval queue (operator token, verified end-to-end locally — list → one-click approve → graph resumed), SSE live run timeline, keyword/source tags on runs, today's-spend + daily-ceiling alert on the cost panel. Deployed console verified "API connected" with the queue rendered.
6. **Research Agent web-wide search**: `search_web` MCP tool (DuckDuckGo HTML, keyless), live-verified; `MAX_RESEARCH_STEPS` 16→18.
7. **Story pages** (`/showcase/ptp-xxx`): problem, evidence, analyst verdict, human decision, product vision, build (stack/features/QA rounds), full timeline replay. PTP-011's is live and seeded (`web/src/lib/seed-story.ts` mirrors the real record, same pattern as `cases.ts`).
8. Tests 56 → **78**, all green; ruff clean; `pnpm lint`/`build` clean; three commits pushed; Render auto-deployed the API (v1.1 confirmed live); web deployed to Vercel twice (user-approved).

#### Shipped but needs a decision/step from the user
- **Real email delivery** (the user explicitly asked for review + product-ready emails): everything is wired including the new `notify.send_product_ready`; the ONLY missing piece is a `RESEND_API_KEY` (free at resend.com) in `.env` and in Render's env vars, plus `REVIEW_EMAIL_TO` on Render. Until then both emails log to the server console.
- **Production full loop**: prod's pipeline pauses at the human gate correctly (run `fb569f7e…` awaiting review). Approving it needs the operator key (Render dashboard `API_TOKEN`) pasted into the live console's queue — and prod builds will skip publish until `VERCEL_TOKEN` is set in Render's env.
- **Production data durability**: the Render DB was found EMPTY (2026-07-07's runs gone). Free-tier reset suspected. Seeded fallbacks carry the public site regardless; paying for the starter disk is the alternative.
- Local pending reviews left intentionally undecided for the user: PTP-017/018/019 ("prompt caching strategies" search) + 4 older ones — visible in the local console queue.

#### Deliberately deferred
- Semantic keyword dedupe (exact-normalized only), Postgres migration, prompt versioning, visual graph state in console, Reddit source, OKF principle library — all unchanged from §11/§12.
- A `ptp_number` UNIQUE constraint on migrated SQLite DBs (ALTER can't add one; single-writer assignment logic guarantees it in practice — Postgres migration adds the real constraint).

#### Important implementation details this session adds (do not lose)
- **`venture.agents._completion` is a second seam** next to `_structured` — same module-attribute-access rule for callers and tests (test_build monkeypatches both).
- **The SQLite micro-migration** (`db/engine._apply_additive_columns`) runs before `create_all` at every boot — additive nullable columns only; anything fancier means Alembic time.
- **Never let the LLM own file structure**: paths (`scaffold_targets`), component shape (`consolidate_components`/`ensure_browser_components`), asset tags (`link_assets`), and id existence (`undefined_dom_ids`) are all code. Any new build-stage behavior should ask "can code decide this?" first.
- **The public search endpoint is deliberately open**; its protection is the layered spend controls, all enforced BEFORE any LLM call. Don't add a bearer token to it — that deletes the feature.
- **`/api/v1/reviews/pending` returns live capabilities (tokens)** — it must stay operator-protected forever.
- The Vercel token in `.env` authenticates as team `asmq333`'s user (`dsharp0707`); product deploys create projects named `ptp-NNN-slug` in that team.

---

### Previous session record (2026-07-07, Phase A: production foundation + real public deployment)

This was the single biggest infra jump the project has had: it went from "everything runs on localhost" to "deployed and publicly reachable" in one session, executed in two parts — first the Phase A build-out (Docker/K8s/CI/Promptfoo/cost tracking), then, at the user's explicit follow-up request, actually deploying it.

**The project is now live: web at https://protopro.vercel.app, API at https://protopro-api.onrender.com — confirmed wired together (the deployed console shows "API connected," not the seeded fallback).**

1. **Lint baseline**: ruff added (`pyproject.toml`'s `[tool.ruff]`, py313/E/F/I/B/UP, `E501` ignored — prompts run long legitimately). 27 findings, 25 auto-fixed; two hand-fixed and worth remembering: `zip(components, results, strict=True)` in `build/graph.py`'s fan-out (silent-truncation risk if a future change ever made the two lists mismatched length), and `resilience.with_retry` converted from `TypeVar` to a PEP 695 generic (`with_retry[T](...)`).
2. **Docker, verified by actually running it**: `Dockerfile` (API: `uv` builder stage → `python:3.13-slim` runtime, non-root, `DATA_DIR=/app/data`) and `web/Dockerfile` (Next.js `output: "standalone"`, added to `next.config.ts` — wasn't there before). `docker compose up --build` was run for real: both containers reported `healthy`, and the containerized web's `/console` page rendered "API connected" over the compose-internal network — not just "the images built."
   - **A real bug found by this**, not by unit tests: `db/engine.py` parsed the SQLite directory via `url.rsplit("///", 1)` on `database_url`. That's correct for a relative `data_dir` (3-slash URL) but wrong for a POSIX *absolute* one (4-slash URL, `sqlite+aiosqlite:////app/data/...`) — the rsplit strips the leading slash, yields a relative path, and the API container crash-looped (`PermissionError: 'app'`) on first boot. Windows dev-machine paths never exercise this, which is exactly why 48 previously-green tests missed it. Fixed by using `settings.data_dir` directly. **If this code is touched again, test it against a POSIX absolute path explicitly, not just whatever the dev machine's paths look like.**
   - Also fixed live: `docker compose up` initially failed with "port is already allocated" — an unrelated `wc26-mlops` Docker stack already had 8000/5000/8080 bound on this machine. Solved by making the host ports overridable (`${API_PORT:-8000}`/`${WEB_PORT:-3000}` in `docker-compose.yml`), not by touching the other stack.
3. **`GET /api/v1/health`** (new endpoint): a real `repo.ping()` → `SELECT 1`, not a liveness stub; 503 when the DB is unreachable. This is the target every healthcheck/probe added this session points at (Dockerfile `HEALTHCHECK`, Compose `depends_on: condition: service_healthy`, K8s readiness/liveness probes).
4. **Kubernetes manifests** (`deploy/k8s/`): namespace, ConfigMap, a Secret *template* (`secret.example.yaml` — the real `secret.yaml` is gitignored, never created this session since there's no cluster to apply it to), API Deployment+PVC+Service (**deliberately `replicas: 1` + `strategy: Recreate`** — SQLite is single-writer, and the manifest says so via a comment rather than silently inviting an autoscaler to corrupt data), web Deployment+Service+HPA (2-5 replicas, CPU-triggered — safe because the web tier is stateless-by-design since Phase 2's seeded-fallback contract), and an Ingress. Tied together with `kustomization.yaml`, validated via `kubectl kustomize deploy/k8s` (renders clean). **Never applied to a live cluster** — none was available on the dev machine; this is demonstrated-but-unexercised infrastructure, be upfront about that distinction if asked.
5. **CI/CD**: `.github/workflows/ci.yml` runs on every push (ruff, pytest, eslint, `next build`, both Docker builds with GHA layer caching, a Promptfoo *config schema* check — zero LLM calls, zero cost). `.github/workflows/promptfoo.yml` is separate: `workflow_dispatch` + weekly schedule only, runs the real live-eval suite, and skips gracefully with a `::notice::` if `GROQ_API_KEY` isn't configured as a repo secret (same honest-degradation pattern the homegrown eval and OKF write-up already established). **Unverified**: whether `GROQ_API_KEY` was actually added as a GitHub Actions secret — if not, `promptfoo.yml` will just skip forever, which is correct behavior but worth confirming intentionally rather than assuming.
6. **Promptfoo** (`promptfooconfig.yaml` + `src/p2pops/evals/promptfoo_provider.py`, ADR-0008) — the last of the three originally-named LLMOps tools that had zero integration, now live. The provider is an `exec:`-protocol script (protocol details reverse-engineered from promptfoo's own source in `node_modules`, not guessed) that dispatches each test case to the REAL `analyze_idea`/`validate_problem` functions — not a copied prompt string, which would only catch drift between the copy and the original, never a real regression. 5 scenarios (Analyst: guardrail-blocks-spam, strong-problem-scores-well, vague-problem-scores-low; Validator: strong-evidence, no-evidence-lowers-confidence). **Run live against the real Groq key in `.env`: first pass was 4/5** — the "vague non-problem" scenario failed because the guardrail *correctly* blocked the deliberately-vague test input before scoring ever ran (a legitimate outcome the original assertion didn't account for). Fixed the assertion to accept either a guardrail-block or a low score as valid, re-ran: **5/5.** This exact fix is visible in the current `promptfooconfig.yaml` if you want the precise before/after.
   - Local promptfoo/vercel CLI runs on this machine needed `npm_config_cache=<fresh dir>` — the default Windows npm cache was corrupted (`ECOMPROMISED`/"Lock compromised", persisted across `npm cache clean --force`). Not a project bug; a one-time environment quirk, documented in §13's troubleshooting in case it recurs.
7. **LLM cost tracking** (ADR-0009): new `LlmCall` table, `src/p2pops/pricing.py` (a dated USD/1M-token list-price table; an unknown model prices at $0.00 rather than raising — pricing must never be able to break agent execution), `src/p2pops/cost_tracking.py` (`record_usage`, best-effort, logs-and-swallows any failure). Wired into all three call-site shapes: `venture.agents._structured` (covers venture AND build-squad — one shared seam per ADR-0006), the Analyst's scorer, and the Research Agent's per-message ReAct capture.
   - **The `include_raw=True` trap, real and non-obvious**: capturing token usage requires `model.with_structured_output(schema, include_raw=True)`, but that flag silently changes LangChain's failure contract — instead of raising on malformed model output, it returns a dict with a `parsing_error` key. Left unhandled, this would have **silently defeated ADR-0005's retry-on-`tool_use_failed` logic**, since the exception `resilience.with_retry` classifies on would simply never be raised anymore. Both call sites (`venture/agents.py::_structured`, `agents/analyst.py`) now explicitly check `result.get("parsing_error")` and re-raise it. If a third `include_raw=True` call site is ever added, it needs the same check — this is exactly the kind of regression that stays invisible until a live model hiccups.
   - `GET /api/v1/costs` + a new console cost panel (spend/calls/tokens, broken down by agent and by model). **Live-verified**: ran a real discovery pipeline, recorded 6 LLM calls / 5,965 tokens / ~$0.00077, confirmed correct in both the raw API response and the rendered console.
8. **Actually deployed** (this was the second half of the session, at the user's explicit follow-up request — Phase A alone doesn't get you a public URL):
   - **Web → Vercel.** Linked `web/` as project `asmq333/protopro` (scope `asmq333` — the only team on the provided token), deployed via `vercel deploy --prod`. Confirmed live: `curl https://protopro.vercel.app` → 200, `/console` renders.
   - **API → Render**, via a Blueprint (`render.yaml`, committed to the repo, then connected through the Render dashboard's "New → Blueprint" flow — the user did this step manually since it needed their Render login). Docker-based (`dockerfilePath: ./Dockerfile`), `starter` plan with a 1GB persistent disk at `/app/data`, `API_TOKEN` set to `generateValue: true` so Render mints one automatically rather than it defaulting to open. Confirmed live: `curl https://protopro-api.onrender.com/api/v1/health` → `{"status":"ok","database":true}`.
   - **Wired together**: added `PROTOPRO_API_URL=https://protopro-api.onrender.com` as a Vercel Production env var (`vercel env add`), redeployed, and confirmed the deployed console now shows "API connected" instead of the seeded-fallback "API offline" state — i.e., the Vercel-hosted server component is successfully calling the Render-hosted API over the public internet, not just that both happen to be up independently.
   - **A Vercel access token was pasted into this chat** to authorize the CLI deploys. The user was told to rotate it at vercel.com/account/tokens afterward — **whether that rotation actually happened is unconfirmed**; treat any token value that might still be sitting in shell history/`.env` on this machine as potentially stale/revoked, don't assume it still works.
9. Tests: 48 → 56 (health endpoint, pricing estimation, cost aggregation). `ruff check` clean. `pnpm lint`/`pnpm build` clean. Everything committed and pushed to `https://github.com/dilipna/Pro2ProAgent` (the repo had no remote before this session — the user supplied the URL mid-session).

### Files modified/added this session (Phase A)
- **Added (backend)**: `src/p2pops/cost_tracking.py`, `src/p2pops/pricing.py`, `src/p2pops/evals/promptfoo_provider.py`, `tests/test_pricing.py`, `docs/adr/0007-containerization-and-deployment.md`, `docs/adr/0008-cicd-and-promptfoo.md`, `docs/adr/0009-cost-tracking.md`.
- **Added (infra)**: `Dockerfile`, `.dockerignore`, `web/Dockerfile`, `web/.dockerignore`, `docker-compose.yml`, `docker-compose.dev.yml`, `deploy/k8s/{namespace,configmap,secret.example,api,web,ingress,kustomization}.yaml`, `deploy/README.md`, `.github/workflows/ci.yml`, `.github/workflows/promptfoo.yml`, `promptfooconfig.yaml`, `render.yaml`.
- **Modified (backend)**: `src/p2pops/db/engine.py` (the `data_dir` parsing fix), `src/p2pops/db/repository.py` (`ping()`, `record_llm_call`, cost aggregation queries), `src/p2pops/api/app.py` + `api/schemas.py` (`/health`, `/costs`), `src/p2pops/venture/agents.py` + `agents/analyst.py` + `agents/research.py` (cost-tracking calls + the `include_raw`/`parsing_error` fix), `src/p2pops/resilience.py` (PEP 695 generic), `src/p2pops/build/graph.py` (`zip(..., strict=True)`), `src/p2pops/db/models.py` (`LlmCall` table), `pyproject.toml` (ruff config, `p2pops-promptfoo-provider` script), `.gitignore` (`deploy/k8s/secret.yaml`).
- **Modified (frontend)**: `web/next.config.ts` (`output: "standalone"`), `web/package.json` (`packageManager` pin), `web/src/app/console/page.tsx` + `web/src/lib/api.ts` (cost panel).
- **Modified (infra, post-deploy)**: none beyond the Vercel dashboard env var and the Render dashboard secrets — both set through each platform's UI, not committed.
- **First-ever commit + push** to `https://github.com/dilipna/Pro2ProAgent` (previously no git remote existed at all).

### Exact next task for the next session
Per the current Roadmap (§11): (1) confirm which Render plan is actually live (`starter`+disk as `render.yaml` specifies, or `free` — changes the "data persists across redeploys" claim materially) and confirm `API_TOKEN`/`GROQ_API_KEY` are genuinely set in the Render dashboard, not just implied by the blueprint; (2) real file-tree persistence for build-squad scaffolds; (3) wire GitHub Actions to auto-deploy on merge instead of the current manual `vercel deploy`/Render-dashboard flow.

### Remaining blockers
None functionally — the deployment is live and verified end-to-end. Two things need the user's confirmation, not more engineering: whether the pasted Vercel token was rotated, and which Render plan is actually active.

### Important implementation details a new session must know
- **The API is pinned to 1 replica in every single deploy target** (Compose, K8s, Render) — this is not a limitation someone forgot to fix, it's SQLite's single-writer constraint made explicit. Do not "fix" this by bumping replica counts without first doing the Postgres migration (§11).
- **`db/engine.py` must use `settings.data_dir` directly for the SQLite parent-directory `mkdir`, never re-derive it from `database_url` via string splitting** — see item 2 above; this exact bug already shipped once.
- **Any new `with_structured_output(..., include_raw=True)` call site must check `result.get("parsing_error")` and re-raise it**, exactly like `venture/agents.py::_structured` and `agents/analyst.py` do — otherwise it silently defeats ADR-0005's retry contract for that call site.
- **`ci.yml` never calls a real LLM; `promptfoo.yml` does, and only on `workflow_dispatch`/weekly.** Don't merge prompt/schema changes to `venture/agents.py` or `agents/analyst.py` assuming the push-triggered CI caught a live regression — it didn't, by design. Run `promptfoo eval` locally, or trigger `promptfoo.yml` manually, before trusting a prompt change.
- **The deployed frontend calls the API server-side only** (Next.js server components → API), never from the browser — so the API's CORS allowlist (still just `localhost:3000`/`127.0.0.1:3000`) hasn't needed `https://protopro.vercel.app` added. If any client-side `fetch` to the API is ever introduced, that CORS list needs updating or it will fail silently in the browser only (server-side rendering would still work, making this an easy bug to miss).
- **Everything from the Phase 3 handoff below still applies** (the `venture.agents._structured` module-attribute-access rule, `MAX_QA_ROUNDS`/`MAX_REFINEMENT_ROUNDS` semantics, build-squad's CLI-only trigger, the Phase 2 seeded-fallback/CWD-relative-`data_dir` notes) — nothing this session changed those, it only added a deployment layer on top.

---

### Previous session record (2026-07-06, Phase 3: observability proof + evals + build-squad + console deep views)

The user supplied `LANGSMITH_API_KEY`/`LOGFIRE_TOKEN` and asked for everything open from the Phase 2 handoff to be done in one pass. Given the size (four separate initiatives, one a brand-new subgraph), this session used `EnterPlanMode` first — two research passes (an Explore agent over `venture/agents.py`/`scoring.py`/test patterns/ADR format, then a Plan agent that stress-tested the build-squad design specifically) before writing any code. The approved plan is preserved at `C:\Users\Dilip\.claude\plans\silly-munching-wilkes.md` on this machine if the reasoning behind a decision below needs more detail than fits here.

1. **Observability verified, not just wired** — the single item blocking on the user was unblocked first. Ran `p2pops-pipeline` live; confirmed via LangSmith's REST API (`/runs/query` against the real session id) that the run's traces landed with matching run IDs/timestamps/node names, and Logfire's `configure()` printed a real working project URL (`https://logfire-us.pydantic.dev/dsharp/starter-project`) with no auth error. Re-confirmed against the build-squad run too (below) — its own node names (`qa`, `route_after_qa`, `mark_needs_revision`) showed up in LangSmith as well. **No code changes** for this item.
2. **Evals started** (`src/p2pops/evals/analyst_eval.py`, `p2pops-eval` CLI): turns `Review.decision` (already surfaced directly on `Idea.status` as `approved`/`declined` — no join needed) into an agreement-rate + score-comparison report. No `BRAINTRUST_API_KEY` exists, so this is dependency-free rather than force-adopting an unavailable hosted tool. Honest about scope: measures the Analyst's *precision*, not recall (analyst-rejected ideas never reach a human today). New `repo.reviewed_ideas()` helper; `tests/test_evals.py` (3 tests, pure DB aggregation, no LLM/seam needed).
3. **Build-squad subgraph shipped and live-verified** (`src/p2pops/build/`: `schemas.py`, `agents.py`, `scoring.py`, `graph.py`; new `Build` DB model + repository functions; `runner.execute_build`/`start_build`; `GET/POST /api/v1/builds` + `build` field on `OpportunityDetailOut`; `p2pops-build` CLI; ADR-0006; `tests/test_build.py`, 4 scenarios). Mirrors venture pipeline's every invariant (LLM produces artifacts/code decides, one shared `_structured` seam, bounded honest-failure loop, per-item containment) — full design reasoning in ADR-0006, don't re-derive it. **Critical implementation detail**: `build/agents.py` calls the shared seam via `from ..venture import agents as venture_agents` then `venture_agents._structured(...)` (module-attribute access) — never `from ..venture.agents import _structured` — because the latter's name-binding-at-import-time would silently defeat `monkeypatch.setattr(p2pops.venture.agents, "_structured", fake)` in tests, which would then make real (costly) LLM calls without anyone noticing. Verified this crosses correctly by the test suite passing at all. **Trigger is deliberately CLI/protected-POST only, never a public button** — `/console` is unauthenticated and labeled "Internal · read-only"; a public trigger for a paid LLM pipeline would contradict that. **Live-verified** against the real "TrustLayer SDK" opportunity: PM → 7 features, Architect → 4 components, Engineer scaffolded all 4 (the `scaffold_target()` keyword heuristic picked `main.py`/`schema.sql`/`README.md` correctly, including the fallback case), QA blocked round 1 (2 real critical issues — stub methods that don't call the real API), `revise` correctly re-ran only the 2 named components, QA blocked again round 2, and — `MAX_QA_ROUNDS` exhausted — the build **honestly landed on `needs_revision`**, not a silently-accepted `complete`. This is the build-squad equivalent of venture pipeline's own celebrated "2 honest parks" from Phase 1.5: the bounded-loop design working exactly as intended.
   - **A real bug was found and fixed while testing offline** (not live): `MAX_QA_ROUNDS` originally set to `1` following the *word* "one revision round" too literally, but `route_after_qa` mirrors venture's `route_after_stress` exactly (`round_index < MAX`), and venture's own convention is "MAX = total rounds," not "MAX = revisions allowed." At `1`, zero revisions would ever fire. Fixed by setting `MAX_QA_ROUNDS = 2` (exactly one revision, matching intent) rather than changing the comparison operator — keeps the routing code identical to venture's, only the constant's value differs. If you ever touch `MAX_REFINEMENT_ROUNDS` or `MAX_QA_ROUNDS`, remember: the constant equals the total attempt count, not the extra-round count.
4. **Console deep views** (frontend-only, zero new backend surface beyond what build-squad already added): `web/src/app/console/runs/[id]/page.tsx` (event timeline + idea list, from the existing `GET /api/v1/runs/{id}`) and `web/src/app/console/opportunities/[id]/page.tsx` (parses the `OpportunityDossier` JSON — vision/ranking/gates — plus, if a build exists, the `BuildDossier` — plan/architecture/scaffold files as `<details>`/QA verdicts; shows a plain "not yet scaffolded" hint, never a button, when none exists). `web/src/lib/api.ts` gained `getRuns`/`getRun`/`getOpportunity`/`getBuild`. Console's own landing page gained "Recent runs"/"Recent opportunities" lists linking into these, and the stale "build-squad subgraph lands next" copy was fixed.
5. **Verified live, end to end, both API states**: `pytest` 48/48 (was 37); `p2pops-build` completed live as described above; both new API endpoints and the updated opportunity endpoint returned correct data via curl; both new console routes rendered the real data correctly (`curl` checks matched component names, statuses, event agent names); with the API stopped, the run-detail route correctly `notFound()`s (404, no crash) and the landing page keeps serving its cached shell. `pnpm build`/`pnpm lint` both clean.
6. Fixed a small pre-existing honesty issue found along the way: the approval email's copy said "the build squad takes it from here," describing the *venture pipeline* (the actual next automatic stage) — now says "the venture pipeline takes it from here," since build-squad is a separate, later, manually-triggered stage.

### Files modified/added this session (Phase 3)
- **Added (backend)**: `src/p2pops/build/{__init__,schemas,agents,scoring,graph}.py`, `src/p2pops/build_cli.py`, `src/p2pops/evals/{__init__,analyst_eval}.py`, `docs/adr/0006-build-squad-subgraph.md`, `tests/test_build.py`, `tests/test_evals.py`.
- **Added (frontend)**: `web/src/app/console/runs/[id]/page.tsx`, `web/src/app/console/opportunities/[id]/page.tsx`.
- **Modified (backend)**: `src/p2pops/db/models.py` (`Build` model), `src/p2pops/db/repository.py` (build + `reviewed_ideas` functions), `src/p2pops/runner.py` (`execute_build`/`start_build`/`get_build_pipeline`), `src/p2pops/api/schemas.py` + `api/app.py` (build endpoints, opportunity handler rewrite, misleading-copy fix), `pyproject.toml` (`p2pops-eval`, `p2pops-build` scripts), `tests/conftest.py` (`make_idea` gained an optional `score` kwarg), `tests/test_api.py` (5 new build-endpoint tests).
- **Modified (frontend)**: `web/src/lib/api.ts` (new types + helpers), `web/src/app/console/page.tsx` (recent activity lists, copy fix).
- **Modified (docs)**: `PROJECT_BRAIN.md` (§2–§7, §11, §12, §14, §15), `implementation-notes.md` (Phase 3 entry).
- **Left behind (needs manual cleanup, unrelated to this session's new code)**: the stray `web/data/protopro.db` from Phase 2 is still there — still safe to delete, still not this session's doing.

### Exact next task for the next session
Per the current Roadmap (§11): Promptfoo is now the last of the three originally-named LLMOps tools with zero integration (Braintrust-equivalent and LangSmith/Logfire are both live) — a prompt-regression CI config across Research/Analyst/venture/build prompts, which also means finally standing up a GitHub Actions workflow at all. After that: real file-tree persistence for build-squad scaffolds (currently DB-JSON-only — readable in the console, not yet `git`-able), and growing the eval dataset past its current small N.

### Remaining blockers
None. (LangSmith/Logfire were the last blocked item; both resolved this session.)

### Important implementation details a new session must know
- **`venture.agents._structured` is now the seam for TWO packages**, not one. Any new module that needs an LLM call (not just `venture/` or `build/`) must call it via module-attribute access on the `venture.agents` module object, never via `from ...venture.agents import _structured`. Get this wrong and tests silently stop being hermetic.
- **`MAX_QA_ROUNDS` (build) and `MAX_REFINEMENT_ROUNDS` (venture) both mean "total rounds allowed," not "extra rounds beyond the first."** `round_index < MAX` is the shared comparison; get the constant's value right relative to that, not the comparison itself.
- **The build-squad trigger is intentionally CLI/protected-POST only.** Do not add a frontend button for `POST /api/v1/builds`, even though the endpoint exists — the console's own "Internal · read-only" framing and the project's HITL-first philosophy both depend on no public UI ever spending LLM budget unilaterally.
- **Everything from the Phase 2 handoff below still applies** (the seeded-fallback contract in `web/src/lib/api.ts`, the `Promise.race`-not-`AbortSignal` timeout reasoning, the `cacheComponents`-not-enabled caching model, the CWD-relative `data_dir` gotcha) — nothing in this phase changed those.

---

### Previous session record (2026-07-06, Phase 2 — kept for context)

1. **Confirmed repo state ahead of the previous handoff**: the console badge fix (previous handoff's task #1) was already committed at `aab6f29` together with this document — do not redo it.
2. **Wired the frontend to the live API** (the previous handoff's next-highest priority):
   - New `web/src/lib/api.ts`: server-side `/api/v1` client — typed mirrors of the API schemas, 2.5s timeout, and every helper returns `null` on any failure so callers fall back to the seeded content in `cases.ts`. The public site renders fully even with the backend down (verified, not assumed).
   - Landing page: hero discovery ticker (live idea titles; needs ≥6 to loop seamlessly, else seed), Showcase (top-3 `shortlisted|approved` ideas by score, approved-first tiebreak; needs ≥3 else seed — a partial grid reads as broken), PipelineStats (ideas analyzed / analyst-shortlisted / discovery runs / opportunity dossiers). All via ISR (`next: { revalidate: 120 }`) — `/` stays statically prerendered, confirmed in build output.
   - Console: new "Live from the run store" metrics strip (runs / ideas analyzed / human-approved / opportunity dossiers) with an explicit API connected/offline indicator; page is `dynamic = "force-dynamic"` with `cache: "no-store"` fetches.
   - `web/.env.example` documents `PROTOPRO_API_URL` (server-side only; blank = `http://127.0.0.1:8000`).
3. **Two Next.js 16 findings that must not be lost** (from the bundled docs in `web/node_modules/next/dist/docs/`, read per `web/AGENTS.md` before coding — both paid off):
   - This project does **not** enable `cacheComponents`, so the *previous* caching model applies: `fetch` defaults to uncached; ISR via `next.revalidate` on fetch; `force-dynamic` for per-request pages. Don't write `use cache` directives here without enabling the flag first.
   - Passing an `AbortSignal` to `fetch` **opts it out of Next's per-render memoization** — which would have silently doubled the `/ideas` request shared by the hero ticker and Showcase. Timeouts in `api.ts` therefore use `Promise.race`, deliberately not a signal. Keep it that way.
4. **Live verification, both directions**: API up → console strip showed the real 14 runs / 9 ideas / 3 approved / 3 dossiers and the landing page revalidated from the seeded build shell to real DB titles within one ISR cycle. API stopped → console renders "API offline" + em-dash values, landing keeps serving the cached page. `pnpm build` (with backend offline — exercises the fallback at build time), `pnpm lint`, and `uv run pytest` (37/37) all clean. No backend code was touched this session.
5. **PROJECT_BRAIN.md updated** (§2, §3, §5, §9, §11, §12, §14, §15) and `implementation-notes.md` gained the Phase 2 entry.

#### Files modified/added that session
- **Added**: `web/src/lib/api.ts`, `web/.env.example`.
- **Modified**: `web/src/components/hero.tsx`, `web/src/components/showcase.tsx`, `web/src/components/pipeline-stats.tsx`, `web/src/app/console/page.tsx`, `PROJECT_BRAIN.md`, `implementation-notes.md`.
- **Left behind (needs manual cleanup)**: a stray empty `web/data/protopro.db` — created when the API was accidentally started from inside `web/` (the CWD-relative `data_dir` gotcha, §12). Safe to delete; the real database is `data/protopro.db` at the repo root.

---

### Earlier session record (2026-07-06, Phase 1.5 — kept for context)

1. **Full Phase 1 + venture pipeline** (already committed at `9e8df96` before this session's continuation): async DB layer, email HITL via LangGraph `interrupt()`, FastAPI service, the entire venture pipeline (evidence, 4 parallel agents, deterministic gates/ranking, bounded red-team/refiner loop, product vision synthesis, `OpportunityDossier` persistence).
2. **This session's work** (committed at `7c79955`, "Add LLM-call resilience layer; fix 5 live bugs; switch Groq default model"):
   - Added Groq as a third LLM provider (user supplied a live key mid-conversation; dropped straight into `.env`, never echoed back).
   - Live end-to-end verification attempts surfaced **five real, distinct bugs**, each root-caused and fixed (not papered over), each with a regression test:
     a. Empty tool-result content (`fetch_article_text` → `""`, `search_hacker_news` → `[]`) produced zero MCP content blocks, which Groq's API rejects. Fixed: both tools now return an explicit non-empty placeholder.
     b. `API_TOKEN=` (blank) parsed as `""` not `None`, silently locking every API request. Fixed generically for every optional secret field via a `field_validator`.
     c. Two uncoordinated retry layers (the OpenAI SDK's own + a homemade one) stacked unpredictable multi-minute waits. Fixed: `max_retries=0` on every chat client; one retry seam (`resilience.with_retry`) is now authoritative.
     d. A Groq 413 ("payload permanently too large for this model's TPM ceiling") reused the exact wording of a retryable 429. Fixed: HTTP status code is authoritative over message text.
     e. A distinct class of 400 (`tool_use_failed`, `json_validate_failed`) is actually a *stochastic* model-output failure, not a structural one — the opposite lesson from (d) — and needed its own explicit retryable classification.
   - Discovered Groq's `openai/gpt-oss-20b` on-demand tier caps at 8,000 tokens/minute (org-wide, sliding window — waiting between requests does not help). Queried the account's actual per-model rate limits directly via the API and switched the default model to `llama-4-scout-17b-16e-instruct` (30,000 TPM), verifying tool-calling and structured-output support live before committing to the switch.
   - Tightened the Research Agent's tool-call budget (`MAX_SEARCH_RESULTS=6`, `MAX_ARTICLE_CHARS=1200`, `MAX_RESEARCH_STEPS=16`) and its prompt (mandatory real `source_url` per idea) — both fixes address failures actually observed live, not hypothetical hardening.
   - **Achieved the first fully clean, live, end-to-end run of the entire system**: `POST /api/v1/runs` → Research Agent found 3 real problems → Analyst scored and shortlisted all 3 → email sent (console adapter) with 3 signed review links → all 3 approved via the actual `/r/{token}/approve` endpoint → graph resumed automatically → venture pipeline ran for all 3 ideas → **2 honestly parked** (unresolved critical stress-test issues after 2 refinement rounds — confirms the bounded-loop/quality-gate design works as intended, this is a feature working correctly, not a failure) → **1 reached `complete`** with a full, coherent `OpportunityDossier` ("TrustLayer SDK" — a CI/CD-native AI trust-evaluation SDK, with named competitors, differentiation, a concrete 90-day execution plan, and success metrics).
   - Test suite grew from 23 → **37 passing tests**.
   - Added `docs/adr/0005-llm-call-resilience-and-groq-model-choice.md` documenting all of the above.
3. **This document** (`PROJECT_BRAIN.md`) was created via full repository re-inspection (every source file, `pyproject.toml`, `package.json`, a grep for TODOs/Docker/CI/Braintrust/Promptfoo/PRAW to confirm gaps by absence, not assumption) plus a grounded (web-searched, not guessed) evaluation of Google's Open Knowledge Format.

### Files modified/added that session
- **Added**: `src/p2pops/resilience.py`, `tests/test_resilience.py`, `docs/adr/0005-llm-call-resilience-and-groq-model-choice.md`, `PROJECT_BRAIN.md` (this file).
- **Modified**: `src/p2pops/config.py` (Groq provider, blank-string validator), `src/p2pops/chat_model.py` (Groq branch, `max_retries=0`), `src/p2pops/agents/research.py` (retry wrapping, step ceiling, source_url prompt fix), `src/p2pops/agents/analyst.py` (retry wrapping), `src/p2pops/guardrails.py` (max_tokens for reasoning models), `src/p2pops/mcp/server.py` (payload caps, empty-result placeholders), `src/p2pops/tools/web.py` (non-empty return guarantee), `src/p2pops/venture/agents.py` (delegate to shared retry seam), `tests/test_config.py`, `tests/test_api.py`, `tests/test_mcp_server.py`, `.env.example`, `implementation-notes.md`.
- **`.env`** (not committed, gitignored): now has a working `GROQ_API_KEY`, `LLM_PROVIDER=groq`, `REVIEW_EMAIL_TO` set to the user's real email.

*(That session's "exact next task" — the console badge fix and frontend wiring — is done; see the Phase 2 record above for the current handoff.)*

### Remaining blockers
Only the observability trace, blocked on a LangSmith/Logfire token from the user. (Historical: Anthropic-direct and OpenRouter both exhausted their credit/balance during earlier sessions — Groq is the funded, working provider now.)

### Assumptions made (Phase 1.5 session)
- That fixing tool outputs to never return empty content, rather than trying to make Groq accept empty content, was the correct fix direction (it is — it's also just better tool design regardless of provider).
- That `llama-4-scout-17b-16e-instruct` is an acceptable default-tier model choice going forward given it was chosen primarily for measured rate-limit headroom on this specific Groq account, not for being the objectively "best" model. If the account's tier/limits change, or if Anthropic/OpenRouter credit is restored, `LLM_PROVIDER` can be flipped back with no code changes — that's the whole point of the abstraction.
- That two "parked" opportunities out of three in the live verification run represents the system working *correctly* (honest quality gating), not a defect to "fix" by loosening the gates. Do not weaken `MAX_REFINEMENT_ROUNDS` or the stress-gate's critical-issue check just to get more `complete` outcomes — that would defeat the point.

### Open questions for the user
- Is a LangSmith or Logfire token available, to finally verify one real trace? (Blocks §11's task #1.)
- Priority: console deep views (run timelines from `RunEvent`/SSE) vs. the build-squad subgraph (bigger, more interview-impressive, but a bigger chunk of new work)?
- Should the console's "Tracing" badge read `wiring` until a real trace is confirmed (§12)?
- Is a Resend API key available/wanted, to move the email HITL off the console/log adapter and onto real email delivery?
- Any interest in the OKF stretch goal (§12) now that it's been evaluated and scoped narrowly, or should the principle library stay as plain Python for now?

### Important implementation details a new session must know
- **The frontend degrades gracefully by contract**: every `web/src/lib/api.ts` helper returns `null` on any failure and every consumer falls back to the seeded content in `cases.ts`. Never let a component render blank/broken because the API is down, and never delete the seed data — it *is* the fallback.
- **Do not pass an `AbortSignal` to `fetch` in the web app** — Next.js drops per-render memoization for signal-carrying fetches (documented in the bundled Next 16 docs), which would duplicate the `/ideas` request shared across components. `api.ts` uses `Promise.race` for timeouts for exactly this reason.
- **`cacheComponents` is not enabled** in `web/next.config.ts` — the previous caching model applies (`next.revalidate` on fetch, `dynamic = "force-dynamic"` for per-request pages). Read `web/node_modules/next/dist/docs/` before frontend work; it has already caught two would-be bugs.
- **Start `p2pops-api` from the repo root** — `data_dir` is CWD-relative (§12).
- **The `_structured` seam** (`venture/agents.py`) is the one place all venture-pipeline LLM calls flow through — it's also the exact function tests monkeypatch to run the entire venture graph offline, deterministically. Any new venture agent must go through it.
- **`request_review` must never move inside `human_gate`** — LangGraph re-executes an interrupted node from the top on resume, so if the review-token-creation and email-sending logic were inside the same node as the `interrupt()` call, resuming would re-send the email and re-create tokens. This is why they're two separate nodes.
- **Never loosen `_is_retryable`'s "4xx (except 429) = don't retry"** default without a specific, named, observed exception (like the two Groq generation-error codes) — the whole point of this module is that it was built from *observed* failures, not theoretical ones. Speculative retryability additions should be resisted.
- **The Groq model choice is capacity-planning, not just "pick a good model"** — if switching providers/models again, always query the account's actual `x-ratelimit-limit-tokens` header first (see the curl commands used in this session, preserved in ADR-0005's context) rather than assuming.
