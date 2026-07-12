# ProToPro — Problems in. Products out.

An autonomous product company run by AI agents — **live, deployed, and it has
already shipped real products.**

| | |
|---|---|
| 🌐 Public site (showcase + search) | **https://protopro.vercel.app** |
| 🛠 Operations console | **https://protopro.vercel.app/console** |
| ⚙️ API | **https://protopro-api.onrender.com** (`/api/v1/health`) |
| 📦 First shipped product (PTP-011) | **https://ptp-011-trustlayer-sdk.vercel.app** |
| 📦 Second shipped product (PTP-020) | **https://ptp-020-llm-billing-ledger-system-o.vercel.app** |

## ⚡ Starting a new development session?

**Open `PROJECT_BRAIN.md` and read §15 (Session Handoff) first** — it is the
single source of truth, updated at the end of every significant session, and
lets a fresh session continue with zero context loss. Say:

> "Read PROJECT_BRAIN.md and continue development."

Supporting docs: `implementation-notes.md` (chronological phase log) and
`docs/adr/0001…0010` (every non-obvious decision, with reasoning).

## What it does — the full closed loop

```
DISCOVER            VALIDATE              APPROVE           BUILD                    PUBLISH
Research Agent  →   Guardrail + dedupe →  Human gate     →  PM → Architect →      →  Vercel deploy
(HN + web search,   + Analyst scoring     (email links      Engineer → QA            + smoke check
 or a visitor's     (conviction 0-100)    or the console    (bounded revise loop)    + showcase card
 keyword search)                          approval queue)                            + story page
```

Every stage is real and live-verified:

1. **Discover** — a LangGraph ReAct agent works Hacker News and the general web
   (DuckDuckGo) as MCP tools. Visitors can scope a run from the homepage
   **search box** (rate-limited, guardrailed, cost-capped — see below).
2. **Validate** — NeMo Guardrails input rail → ChromaDB semantic dedupe →
   structured Analyst scoring. Validated problems get a sequential public
   **`PTP-XXX` number**.
3. **Approve** — nothing is built without a human. Review requests arrive by
   **email** (Resend) and in the console's **Pending approvals** queue
   (operator-token gated, one-click approve/reject).
4. **Build** — on approval the venture pipeline (evidence → parallel analysts →
   deterministic gates → red-team ⇄ refiner → product vision) runs, and if it
   survives, the **build squad auto-runs**: PM → Architect → Engineer → QA
   produce a *working* client-side web app (each product with its own distinct
   visual identity). Weak ideas get honestly **parked** — the gates kill things.
5. **Publish** — the QA-passed product deploys to its own `ptp-NNN-name.vercel.app`
   URL, gets smoke-checked, flips its showcase card to **Shipped**, gains a
   permanent **story page** (`/showcase/ptp-xxx`), and the operator gets a
   "product is live" email.

## Stack (all live, none aspirational)

| Concern | Tool |
|---|---|
| Multi-agent orchestration | LangGraph — discovery graph (checkpointed, `interrupt()` human gate), venture subgraph, build subgraph |
| Tool exposure | MCP stdio server (`search_hacker_news`, `search_web`, `read_article`) |
| Guardrails | NeMo Guardrails (idea rail + keyword-search rail) |
| Model routing | Anthropic / OpenRouter / Groq — one `.env` switch (Groq is the funded provider) |
| Memory / dedupe | ChromaDB, local ONNX embeddings |
| Resilience | Homegrown rate-limit-aware retry (`resilience.py`, built from 5 live incidents — ADR-0005) |
| API | FastAPI + SSE streaming, SQLite (async SQLAlchemy) |
| Cost tracking | Per-call `LlmCall` ledger + daily spend ceiling + console panel |
| Observability | LangSmith + Pydantic Logfire (verified live) |
| Evals | Promptfoo (calls the real agent functions) + homegrown analyst-agreement eval |
| Frontend | Next.js 16 + Tailwind v4, custom "obsidian & ember" design system |
| Infra | Docker (both tiers), GitHub Actions CI (green), K8s manifests, Render (API, auto-deploys on push) + Vercel (web) |

## Public search spend controls (the endpoint is open by design)

Per-client hourly limit → 24h keyword dedupe → global daily run cap → daily
LLM cost ceiling — all enforced **before any token is spent**, all audited in
the `search_requests` table. Everything a search finds still stops at the
human gate.

## Setup

```bash
uv sync && cp .env.example .env       # fill in GROQ_API_KEY (or another provider)
uv run p2pops-api                     # API on http://localhost:8000 (run from repo root!)
cd web && pnpm install && pnpm dev    # site on http://localhost:3000

uv run pytest                         # 78 tests, no LLM calls (live tests skip without a key)
uv run p2pops-pipeline "some topic"   # one full discovery run from the CLI
uv run p2pops-build <opportunity_id>  # (re)build one venture-complete opportunity
docker compose up --build             # both tiers in containers
```

Key `.env` entries beyond provider keys: `RESEND_API_KEY` + `REVIEW_EMAIL_TO`
(real approval/product emails; console-logged without them), `VERCEL_TOKEN`
(product publishing; publish skips honestly without it), `API_TOKEN` (operator
key for mutating endpoints + the console approval queue),
`DAILY_COST_CEILING_USD` and the `SEARCH_*` limits.

## Where things stand (end of Phase B, 2026-07-11)

**Done and live:** the entire loop above, two shipped products, public keyword
search, console approval queue + SSE live run timelines + cost alerts, story
pages, PTP numbering, CI green, 78 tests.

**Known open items** (detail in `PROJECT_BRAIN.md` §11/§15):
- Production (Render free/starter tier) is slow enough that discovery runs can
  stall, and any redeploy kills in-flight runs — the two shipped products were
  built by the local pipeline against the same codebase. A paid Render tier
  and/or a startup sweep for orphaned `running` runs are the fixes.
- `RESEND_API_KEY`/`VERCEL_TOKEN` must be present in Render's env for
  production emails and production publishes.
- Postgres migration, semantic keyword dedupe, prompt versioning — deferred.

## Repository map

```
src/p2pops/        agents/ (research, analyst) · venture/ · build/ · mcp/ · tools/
                   graph.py (discovery) · runner.py (lifecycle) · publish.py (deploy)
                   guardrails.py · resilience.py · cost_tracking.py · notify.py
web/src/           app/ (landing, console, story pages, API proxies) · components/ · lib/
docs/adr/          ADR-0001 … ADR-0010 — the reasoning behind every big decision
PROJECT_BRAIN.md   ← single source of truth; §15 = session handoff
```
