# PROJECT_BRAIN.md — ProToPro Single Source of Truth

> **How to use this file:** open a fresh Claude session and say "Read PROJECT_BRAIN.md and continue development." Everything needed to pick up work with zero prior context lives here. **Section 15 (Session Handoff) is the most important section and is updated at the end of every significant work session** — read it first if you're in a hurry.
>
> Last verified against the actual codebase: **2026-07-06**, by direct inspection (every source file read, `pytest` run, a full live pipeline run executed against real APIs and its output inspected). Nothing in this document is aspirational unless explicitly marked "planned" or "not started."

---

## 1. Project Overview

**Name:** ProToPro ("Problem to Product"). Internal Python package/codename: `p2pops` (from the original working title "P2POps") — kept deliberately; renaming is pure churn with no functional value (see §4 decisions).

**Elevator pitch:** ProToPro is an autonomous product-discovery company run by AI agents. It listens for real, recurring pain points across developer communities (Hacker News today; Reddit deferred), validates each one through a guardrailed multi-agent analysis pipeline, pauses for a human's yes/no over email, and — on approval — runs the idea through a second multi-agent "venture pipeline" that produces evidence-grounded market analysis, a ranked set of solution directions, adversarial stress-testing, and a complete product vision. Two independent adversarial gates can and do kill weak ideas honestly (observed live, see §15).

**Vision:** A venture-studio-in-a-box: point it at a domain, let a company of specialized agents do discovery → validation → opportunity synthesis, with a human as the single approval gate and full observability into every agent's reasoning.

**Mission (near-term, honest):** This is currently a **portfolio/demonstration project**, explicitly positioned (per the user's direction) to prove hands-on 2026-grade LLMOps/AgentOps engineering skill for job applications (AI Engineer / LLM Engineer / Applied AI / Agentic AI / MLOps roles). It is being built to production engineering standards (typed schemas, tested gates, real retry/observability logic, ADR-documented decisions) but has **no real users, no deployment, and no revenue** yet.

**Target users (of the eventual product):** founders/venture-studio operators who want AI-assisted opportunity discovery. **Target users (of the project right now):** recruiters and engineers evaluating the codebase, via the public site's Showcase and the discreet `/console` operations view.

**Core problem being solved:**
1. *(Product-level)* Good product opportunities are hiding in plain sight in developer communities; finding, validating, and stress-testing them well is slow, unstructured, and expert-scarce.
2. *(Portfolio-level)* Prove — with a live, working, adversarially-tested system, not slideware — that the builder can design multi-agent orchestration, guardrails, evaluation gates, HITL workflows, and production-shaped observability.

**Resume/interview value proposition:** every piece was chosen to map directly onto a 2026 AI-engineering job description line item: LangGraph orchestration with real conditional routing and a bounded adversarial refinement loop; NeMo Guardrails; a swappable multi-provider LLM layer (Anthropic/OpenRouter/Groq) that survived three real capacity/quota incidents live; a from-scratch rate-limit-aware retry layer with 9 unit tests; async SQLAlchemy + FastAPI + SSE; LangGraph `interrupt()`-based human-in-the-loop with signed single-use tokens; a deterministic, explainable scoring/gating model (not "the LLM decides"); and a fully custom-designed Next.js frontend. See §15 for the specific live incidents and fixes — these are genuine debugging stories, not invented ones, and make excellent interview material.

---

## 2. Repository Analysis

### What currently exists (verified by direct file inspection, 2026-07-06)

**Backend** (`src/p2pops/`, Python 3.13, `uv`-managed):
- A discovery pipeline: Research Agent (LangGraph ReAct agent, tools served over a real MCP stdio server) → Supervisor routing → Analyst (NeMo Guardrails input rail → ChromaDB semantic dedupe → structured LLM scoring).
- A run-infrastructure layer: async SQLAlchemy models, a repository module, a FastAPI service, SSE event streaming.
- An email-based human-in-the-loop gate built on LangGraph's `interrupt()` + a SQLite checkpointer, with signed single-use review-action links.
- A **venture pipeline**: a second LangGraph subgraph that runs once per human-approved idea — parallel evidence-grounded analysis, a curated founder-pattern principle library, deterministic ranking, a bounded red-team/refiner adversarial loop, and a final product-vision synthesis, persisted as a structured `OpportunityDossier`.
- A from-scratch LLM-call resilience layer (rate-limit-aware retry, provider-error classification) built and hardened against **real, live provider failures**, not hypothetical ones.

**Frontend** (`web/`, Next.js 16 + TypeScript + Tailwind v4 + Motion, pnpm):
- A fully custom-designed public landing page ("obsidian & ember" design system) telling the problem→product story, with a live discovery ticker seeded from real pipeline output.
- A discreet `/console` operations page for recruiters, showing pipeline module status plus a live run-store metrics strip.
- **Wired to the live backend API** (Phase 2): a server-side API client (`web/src/lib/api.ts`) feeds the hero ticker, Showcase, pipeline stats, and console metrics from `/api/v1/*`, with the seeded content retained as an automatic fallback whenever the API is unreachable — the public site never breaks because the backend is down.

**Docs**: `docs/adr/` (5 ADRs, the actual engineering decision record), `implementation-notes.md` (a chronological phase log kept during development).

### Strengths
- Real, live-verified correctness, not just passing unit tests: the entire chain (discover → analyze → email → approve → venture-pipeline → dossier) has been run against real hosted LLM APIs end to end, and the failures encountered along the way were root-caused and fixed, with tests added to prevent regression. This is a materially stronger portfolio signal than a project that only ever ran against mocks.
- Deterministic, explainable decision-making layered on top of LLM outputs: `venture/scoring.py` computes ranking and gate pass/fail in plain Python from LLM-supplied sub-scores — reproducible, unit-tested, and not "vibes."
- Every non-obvious engineering decision is written down as an ADR with the reasoning and trade-offs, not just the outcome.
- Test suite (37 tests) covers unit logic (scoring, resilience classification), integration (repository, hermetic ASGI API tests), and full offline graph execution (the venture pipeline's entire happy/rejection/parking paths run for real, with only the LLM call substituted) — a good testing pyramid.

### Weaknesses / gaps (see §3 and §12 for the full itemized list)
- No Braintrust, no Promptfoo — two of the originally-named stack tools are not integrated at all.
- No Docker/Compose, no CI/CD pipeline, no deployment.
- No Reddit source (deferred by explicit user choice, HN-only).
- `llm.py`'s single-caller `complete()` function has no retry/resilience wrapping (documented, deliberate, low-risk gap).

---

## 3. Current Project Status

### Completed
- Milestones 1–3 (pre-pivot): Research Agent + MCP server, Supervisor + Analyst with guardrails/dedupe/scoring, all live-verified.
- Phase 0.5: web foundation, design system, landing page, console shell.
- Phase 1: async DB layer, email HITL gate, FastAPI service, venture pipeline (all agents, scoring, gates, dossier).
- Phase 1.5: Groq provider integration, full LLM-call resilience layer, 5 real bugs found/fixed via live iteration, first fully clean live run of the entire chain including 2 honest parks and 1 complete product vision.
- Console status badges corrected (Runs, Human gate → `live`; committed at `aab6f29` alongside this document's creation).
- Phase 2: frontend wired to the live API — server-side client with timeout + seeded fallback, ISR on the landing page, force-dynamic console with a live metrics strip. Verified live in both the API-up and API-down states.

### In Progress / Partially Implemented
- **Observability**: LangSmith and Logfire are fully *wired* in code (`telemetry.py`) but **no API token has ever been supplied for either** — meaning no trace has ever actually been confirmed to land in a LangSmith or Logfire dashboard. Local Logfire instrumentation (Pydantic validation spans) is visible in logs regardless. (Related honesty note: the console's "Tracing" badge reads `live`, which slightly overstates this — see §12.)
- **Console depth**: the live metrics strip is real, but run timelines / graph state / per-agent cost views are still not rendered (the `RunEvent` data and SSE stream exist and are unconsumed by the UI).

### Planned (explicitly discussed, not started)
- Build-squad subgraph (PM → Architect → Engineer fan-out → QA) for turning an approved *venture opportunity* into actual scaffold code — note this is a different, not-yet-built stage beyond the venture pipeline's product-vision output.
- Evals (Braintrust datasets from human review decisions) and prompt regression testing (Promptfoo in CI).
- Deployment (Docker Compose locally, then a real URL — Vercel + a small Python host).

### Missing
- CI/CD, Docker, any deployment artifact.
- Reddit as a second discovery source (PRAW).
- Any authentication/authorization beyond the optional single bearer token.
- Postgres migration (SQLite is the only datastore; fine at current scale, explicitly logged as a deviation to revisit).

### Blocked
- Nothing is currently blocked. (Historical note: Anthropic-direct and OpenRouter both ran out of credit/balance during development; Groq is the working live provider as of this writing, see §7 and ADR-0005.)

### Overall completion estimate
Roughly **65–70% of a "flagship" version** of this project (discovery + validation + human gate + venture synthesis + resilience + a live-wired frontend, all live-verified) vs. the further-out vision (build-squad code generation, evals-in-CI, deployed public product). As a *portfolio piece demonstrating LLMOps/AgentOps engineering maturity*, the backend and the live site are now both strong; the biggest remaining levers for interview impact are the evals/observability proof (Braintrust/Promptfoo/a real LangSmith trace screenshot) and the build-squad subgraph.

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
  chat_model.py     provider-agnostic LangChain chat model factory
  config.py         pydantic-settings Settings (env-driven, blank-string-safe)
  graph.py          discovery pipeline StateGraph
  guardrails.py     NeMo Guardrails input rail wrapper
  llm.py            plain LiteLLM completion wrapper (bootstrap check only)
  memory.py         ChromaDB semantic dedupe
  models.py         shared pydantic schemas (DiscoveredIdea, AnalyzedIdea, ...)
  notify.py         email HITL notifier (Console/Resend adapters)
  pipeline.py       CLI entrypoint for a single discovery run
  resilience.py     rate-limit-aware retry (the resilience layer, ADR-0005)
  runner.py         run lifecycle: start/execute/resume, owns the checkpointer
  telemetry.py      LangSmith + Logfire wiring

web/src/
  app/              page.tsx (landing), console/page.tsx, layout.tsx, globals.css
  components/       nav, hero, method, showcase, pipeline-stats, footer, reveal
  lib/cases.ts      hand-seeded showcase content (real pipeline output, static)
```

### Data flow
1. `POST /api/v1/runs {topic}` → `runner.start_run` creates a `Run` row, launches `execute_run` as a background asyncio task.
2. `execute_run` invokes the compiled discovery graph (checkpointed by `thread_id=run_id`). Every node appends `RunEvent` rows — this *is* the AgentOps timeline.
3. On reaching ideas worth reviewing, `request_review` creates one `Review` row (a signed random token) per shortlisted `Idea`, emails a summary (or logs it, if no Resend key), and the graph pauses at `human_gate` via `interrupt()`.
4. A human clicks `/r/{token}/approve` or `/reject` → `record_decision` consumes the token (single-use, expiring) and updates the `Idea` status.
5. Once every review for a run is decided, `maybe_resume_after_decision` fires `resume_run`, which resumes the checkpointed graph with `Command(resume=decisions)`.
6. For every **approved** idea, `runner.execute_venture` runs the venture subgraph sequentially (deliberately sequential — a concurrency/cost control knob, not an oversight), producing an `Opportunity` row with the full `OpportunityDossier` JSON.
7. The API and (eventually) the frontend read all of this back through `/api/v1/runs`, `/ideas`, `/opportunities`, `/stats`, and the SSE stream.

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
| Observability | LangSmith, Pydantic Logfire | Wired, **not yet verified against real dashboards** (no tokens supplied) |
| Evals | Braintrust, Promptfoo | **Not integrated** |
| Frontend | Next.js 16, Tailwind v4, Motion | Live, wired to the API (seeded fallback when offline) |
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
| Public landing page | Done, live-wired (ISR, seeded fallback) | Next.js + `/api/v1` | — | Opportunity dossier detail pages | Medium |
| Operations console | Done, live metrics strip (force-dynamic) | Next.js + `/api/v1` | — | Run timelines / graph view from `RunEvent` + SSE | High |
| Build-squad code generation | **Not started** | — | PM/Architect/Engineer/QA (planned) | Whole new subgraph | High (biggest remaining "wow" feature) |
| Evals (Braintrust) | **Not started** | — | — | Turn human review decisions into eval datasets | Medium |
| Prompt regression CI (Promptfoo) | **Not started** | — | — | GitHub Actions job | Medium |
| Deployment | **Not started** | Docker, hosting | — | Docker Compose first, then a real URL | Medium |

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

All share a uniform contract: **structured input context (idea + upstream artifacts) → exactly one structured output schema, never free text**; temperature 0; routed through `venture.agents._structured` (the single LLM-call seam, wrapped by `resilience.with_retry`, and the exact seam tests substitute to run the whole graph offline).

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

---

## 7. LLMOps / AgentOps

- **Prompt management**: prompts are Python string constants co-located with the agent that uses them (e.g., `RESEARCH_SYSTEM_PROMPT`, `SCORE_PROMPT_TEMPLATE`, the inline prompts inside each `venture/agents.py` function). **No prompt versioning system** — this is a real gap for a "production-grade" claim; currently, prompt changes are just git history.
- **Observability**: `telemetry.configure_telemetry()` wires LangSmith (env-var based) and Pydantic Logfire (`logfire.span` around every agent call, `logfire.instrument_pydantic()`). **Neither has ever been confirmed against a live dashboard** — no `LANGSMITH_API_KEY` or `LOGFIRE_TOKEN` has been supplied. This is the single most valuable and cheapest next step for interview-readiness: get one real trace screenshot.
- **Logging**: every pipeline/venture node writes a `RunEvent` row (agent, event_type, message, duration_ms) — this is the AgentOps timeline the console is meant to visualize. Currently only consumed via the raw API, not rendered as a UI timeline yet.
- **Monitoring**: none beyond the above (no dashboards, no alerting).
- **Evaluation pipeline**: **not implemented.** Braintrust and Promptfoo are named in the original stack and in ADR discussions but no code exists for either. The honest next step: human review decisions (`Review.decision`) are already exactly the labeled data a Braintrust eval dataset would need — this is a small, well-motivated addition, not a redesign.
- **Guardrails**: NeMo Guardrails input rail on every discovered idea before it reaches scoring (`guardrails.py`). No output rails yet.
- **Human-in-the-loop**: the email gate (ADR-0002), live-verified end to end.
- **Cost optimization**: `max_tokens` caps everywhere (learned the hard way — an uncapped default 64k-token request 402'd against a low-credit account); `MAX_RESEARCH_STEPS`, `MAX_SEARCH_RESULTS=6`, `MAX_ARTICLE_CHARS=1200` all exist specifically to bound spend/context-growth per run; sequential (not parallel) venture-pipeline execution per run is an explicit cost/concurrency control.
- **Model routing**: `LLM_PROVIDER` env switch across Anthropic/OpenRouter/Groq, with per-tier (`default`/`builder`) model selection — this is LiteLLM's and the project's actual "swap providers via config" value proposition, demonstrated for real (all three providers have been live-called this session).
- **Hallucination mitigation**: evidence-grounding requirements baked into prompts (cite E-numbers, no fabricated TAM, no idea without a real `source_url`); clamping validators on numeric scores rather than trusting the model to respect a schema's stated range.

---

## 8. Infrastructure & Deployment

- **Docker**: none. No `Dockerfile`, no `docker-compose.yml` anywhere in the project (only vendored ones inside NeMo Guardrails' own site-packages, irrelevant).
- **CI/CD**: none. No `.github/workflows/` directory exists.
- **Deployment strategy**: not started. Discussed intent (ADR-0001): local SQLite now, Postgres + a real URL (Vercel for the frontend + a small Python host) later, once there's something worth deploying publicly.
- **Secrets management**: `.env` (gitignored), `.env.example` as the template. A real bug was found and fixed here: blank values (`KEY=`) parsed as empty string, not `None`, silently defeating truthy checks — fixed with a `field_validator` (`config.py`, `_BLANKABLE_FIELDS`) that normalizes every optional secret field.
- **Environment variables**: fully enumerated in `.env.example` — provider keys, model overrides, HITL email config, API token, data directory. See §13.
- **Build process**: `uv sync` (Python), `pnpm install` (web). No bundling/packaging beyond that yet.
- **Testing process**: `uv run pytest` — 37 tests, all passing as of the last commit. No test runner configured in CI (because there is no CI).
- **Scalability considerations**: SQLite is a known, deliberate, logged limitation (ADR mentions Postgres migration as future work); sequential venture-pipeline execution per run is a deliberate cost/concurrency throttle, not a scalability ceiling that's been hit yet.

---

## 9. UI / UX Vision

- **Design philosophy**: "obsidian & ember" — a black stage with one glossy maroon signal color, explicitly designed to avoid the generic "AI startup template" look. Full rationale in ADR-0001.
- **Palette**: ink/mist/maroon token scales defined in `web/src/app/globals.css` (`--color-ink-950` through `--color-maroon-200`), plus `glass`, `ember-gloss`, and `grain` utility classes.
- **Typography**: Inter (UI), Instrument Serif italic (editorial/display moments — e.g., the word "Products" in the hero), JetBrains Mono (data/labels), all via `next/font`.
- **Dashboard vision**: the `/console` page is the *current* realization of the "recruiter-facing operations proof" idea — a module grid with live/wiring status per subsystem (Orchestration, Runs, Guardrails, Human gate, Tracing, Evaluations), plus a live run-store metrics strip (runs / ideas / approvals / dossiers, rendered force-dynamic with an explicit API connected/offline indicator). **Still missing the deep views** — run timelines, live graph state, per-agent cost — even though the `RunEvent` data and SSE stream already exist server-side; that's the natural next UI milestone.
- **Components**: `Nav` (with the deliberately discreet Console entry, top-right), `Hero` (CSS-animated, live discovery ticker), `Showcase` (real pipeline-derived case cards), `Method` (5-stage agent production line), `PipelineStats`, `Footer`, `Reveal` (the scroll-triggered motion primitive — deliberately *not* used above the fold, per ADR-0003).
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

---

## 11. Roadmap

### Immediate next tasks (next session should start here)
1. Get one real trace into LangSmith or Logfire (just needs a token in `.env`) and take a screenshot — currently the single cheapest way to close the "wired but never verified" observability gap. **Blocked on the user supplying a token.** While at it, decide whether the console's "Tracing: live" badge should honestly read `wiring` until then (§12).
2. Console deep views: render the `RunEvent` timeline (data + SSE stream already exist and are unconsumed) — the natural next UI milestone now that live metrics flow.
3. Or jump to the build-squad subgraph (the biggest remaining feature gap) if the user prefers feature depth over UI polish.

### Short-term milestones
- Braintrust: turn `Review.decision` records into a labeled eval dataset; a first offline eval of the Analyst's scoring against human agreement.
- Promptfoo: a config covering the Research/Analyst/venture prompts, wired into a GitHub Actions job (which also means: finally add a CI workflow at all).
- Docker Compose for local one-command startup (API + web).

### Medium-term milestones
- Build-squad subgraph: PM → Architect → Engineer (parallel fan-out) → QA reflection loop, turning a `complete` `OpportunityDossier` into an actual scaffolded repo — this is the single biggest remaining feature gap vs. the original full vision.
- Postgres migration (swap the one `database_url` connection string; schema is already ORM-defined, no rewrite needed).
- Real deployment: Vercel (web) + a small always-on host for the API/worker.

### Long-term vision
- Cross-run learning: venture agents drawing on a vector store of past `OpportunityDossier`s (RAG over the project's own history), not just per-run evidence.
- Multi-topic/scheduled discovery runs (currently always manually triggered via POST).
- Reddit as a second discovery source (PRAW, OAuth) — deferred, not abandoned.

### Stretch goals
- OKF-formatted principle library (see §12 below) — small, well-justified, genuinely current (June 2026 spec).
- A real-time console dashboard rendering the `RunEvent` timeline as an actual visual agent-execution graph, not just a JSON list.

---

## 12. Technical Debt

### Known issues
- **Console "Tracing" badge reads `live`** but no LangSmith/Logfire trace has ever been confirmed against a real dashboard (§7) — a mild overstatement, the mirror image of the stale-badge problem fixed at `aab6f29`. Cheapest honest fix: supply a token and verify a trace; otherwise downgrade the badge to `wiring`.
- **`data_dir="data"` is CWD-relative** — starting `p2pops-api` from any directory other than the repo root silently creates a fresh, empty database there (observed live: a stray `web/data/protopro.db` from starting the API inside `web/`). Fine for now; an absolute-path or repo-root-anchored default would remove the foot-gun.
- **`SHORTLIST_THRESHOLD=50` and `MAX_REFINEMENT_ROUNDS=2`** are hardcoded module constants, not configurable — fine for now, explicitly logged as "revisit once there's a dashboard to tune them from" (Analyst) / "a real venture studio kills ideas" (venture, this one is more a design stance than debt).

### Temporary implementations (explicitly logged deviations)
- `Base.metadata.create_all` instead of Alembic migrations (ADR/phase-log-logged deviation from the original "modular monolith" plan) — fine pre-1.0 with a single developer and SQLite; must become Alembic before any real schema change lands on a populated Postgres database.
- Email HITL's Console adapter (prints instead of sending) is what every live test so far has actually exercised — Resend has never been used in anger (no `RESEND_API_KEY` supplied yet).

### Performance improvements
- Venture pipeline runs one approved idea at a time per run (deliberate cost control, not a bug) — parallelizing across ideas (not within one idea's stress/refine loop, which should stay sequential) is a reasonable future lever if run volume grows.

### Refactoring opportunities
- `llm.py`'s `complete()` has no retry wrapping — single caller (bootstrap check), low priority, but should move onto `resilience.with_retry` if it ever gets a second caller.
- The principle library (`venture/principles.py`) is a hardcoded Python list — fine at 8 entries, would benefit from externalization (see OKF discussion, §12-OKF below) if it grows or needs non-engineer editing.

### Security improvements
- No authentication beyond an optional single bearer token on mutating API endpoints (`API_TOKEN`) — fine for a single-operator local/demo deployment, **not sufficient** for any real multi-user or public-write deployment.
- Review action tokens are single-use and expiring (`review_token_ttl_hours`) — good; but the email itself (Console adapter) currently just logs to stdout in dev, meaning anyone with server log access effectively has the approve/reject links. Non-issue in dev; would need real Resend delivery + no log-level secret leakage before any shared/deployed use.

### On Google's Open Knowledge Format (OKF) — evaluated, not blindly adopted

**What it actually is** (verified via web search, since it launched June 12, 2026 — after this assistant's training cutoff, and was *not* assumed or guessed): OKF is a Google Cloud specification (v0.1, still evolving) for representing curated organizational knowledge — a directory of markdown files with YAML frontmatter, following shared conventions — so that knowledge written by one producer can be consumed by AI agents from different vendors without custom translation. It formalizes the "LLM-wiki" pattern (similar in spirit to `llms.txt`/`CLAUDE.md`-style context files, but standardized and directory-shaped).

**Where it does NOT fit this project** (and would be technology-for-its-own-sake if forced in):
- It is not an orchestration framework — does not touch LangGraph.
- It is not a database format — `Run`/`Idea`/`Opportunity` are transactional relational records, not curated reference knowledge; OKF-ifying them would be a category error.
- It is not an eval or observability framework — irrelevant to the Braintrust/Promptfoo/LangSmith gaps.

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

# --- Observability (never yet verified against a live dashboard) ---
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
```
Note: **blank values are safe** — `config.py`'s `_blank_to_none` validator normalizes `KEY=` to `None` for every optional field, fixing a real bug where this used to silently break auth (ADR-0005).

### Commands
```bash
# Backend
uv run pytest                        # 37 tests
uv run p2pops                        # bootstrap check (one LLM call)
uv run p2pops-research "<topic>"     # Research Agent standalone
uv run p2pops-pipeline "<topic>"     # full discovery pipeline, one CLI run
uv run p2pops-api                    # FastAPI server, http://localhost:8000
uv run p2pops-mcp-server             # MCP server standalone (stdio)

# Frontend
cd web && pnpm dev                   # http://localhost:3000
cd web && pnpm build && pnpm start   # production build
```

### Troubleshooting (real incidents encountered, see ADR-0005 for full detail)
- **"content: minimum number of items is 1" from Groq**: a tool returned empty content — already fixed at the source (`tools/web.py`, `mcp/server.py` never return bare `""`/`[]`), but if a *new* tool is added, apply the same rule.
- **API requests all silently 401 despite no token configured**: check `.env` doesn't have a genuinely non-blank-looking `API_TOKEN=` value with hidden whitespace; the blank-normalization only strips fully-blank strings.
- **A run fails immediately with "research failed after 1 attempt(s)"**: check the underlying error in the API server's log — status 4xx-other-than-429 and `GraphRecursionError` are deliberately not retried; this is very likely a genuine, reproducible problem, not a fluke.
- **A run hangs at `status: running` for a long time then fails with repeated "hit a rate limit" warnings**: the configured provider/model's TPM ceiling is too tight for the workload — check `docs/adr/0005-*.md`'s measured-limits table before assuming code is broken.

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
| `src/p2pops/runner.py` | Run lifecycle, owns the checkpointer | The only place that starts/resumes/executes runs and ventures | Called by `api/app.py` and `pipeline.py` |
| `src/p2pops/db/repository.py` | All SQL | Single place that owns data-access semantics | Used by `runner.py`, `graph.py`, `venture/graph.py`, `api/app.py` |
| `src/p2pops/notify.py` | Email HITL delivery | Implements ADR-0002 | Called by `graph.request_review_node` |
| `src/p2pops/mcp/server.py` | MCP tool server | Makes Research Agent's tools a real, portable MCP service | Connected to by `agents/research.py` via `langchain-mcp-adapters` |
| `web/src/lib/api.ts` | Server-side client for `/api/v1` | Feeds live pipeline data to the site with timeout + seeded-fallback semantics | Used by hero, showcase, pipeline-stats, console |
| `web/src/app/globals.css` | Design system tokens | The entire "obsidian & ember" visual identity | Used by every component |
| `docs/adr/*.md` | Architecture Decision Records | The actual engineering reasoning, not just outcomes | Referenced throughout this document |
| `implementation-notes.md` | Chronological phase log | Session-by-session build history, kept during development | Predecessor/complement to this file |
| `PROJECT_BRAIN.md` (this file) | Single source of truth | Enables a fresh session to continue with zero context loss | — |

---

## 15. Session Handoff — READ THIS FIRST

### What was completed in the most recent session (2026-07-06, Phase 2: frontend↔API wiring)

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

### Files modified/added this session (Phase 2)
- **Added**: `web/src/lib/api.ts`, `web/.env.example`.
- **Modified**: `web/src/components/hero.tsx`, `web/src/components/showcase.tsx`, `web/src/components/pipeline-stats.tsx`, `web/src/app/console/page.tsx`, `PROJECT_BRAIN.md`, `implementation-notes.md`.
- **Left behind (needs manual cleanup)**: a stray empty `web/data/protopro.db` — created when the API was accidentally started from inside `web/` (the CWD-relative `data_dir` gotcha, §12). Safe to delete; the real database is `data/protopro.db` at the repo root.

### Exact next task for the next session
The cheapest high-value move is still **one real observability trace** (LangSmith or Logfire) — but it is **blocked on the user supplying an API token** in `.env`; nothing can be done without it. Ask for the token first. If it isn't available, the two unblocked candidates are, in order of the user's previously expressed engagement: (a) **console deep views** — render the `RunEvent` timeline in the console (the data and the SSE stream already exist and are unconsumed by the UI), or (b) **the build-squad subgraph** (PM → Architect → Engineer fan-out → QA), the biggest remaining feature gap. Also worth an explicit user decision: whether the console's "Tracing: live" badge should read `wiring` until a real trace is confirmed (§12).

---

### Previous session record (2026-07-06, Phase 1.5 — kept for context)

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
