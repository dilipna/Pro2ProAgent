# Implementation Notes

> **2026-07-05 pivot:** the project is now **ProToPro** — a startup-grade
> product, not a portfolio demo. Public site tells problem→product stories;
> a discreet Operations Console exposes the engineering; HITL happens over
> email. Major decisions now live in `docs/adr/`. The log below this banner
> covers the pre-pivot milestones (1–3) plus the ongoing phase log.

## Phase log (post-pivot)

### Phase 1 — Run infrastructure, email HITL, venture pipeline (2026-07-06)
- **DB layer** (`src/p2pops/db/`): async SQLAlchemy 2.0 + aiosqlite. Models:
  `Run`, `RunEvent` (the AgentOps timeline), `Idea`, `Review` (single-use
  emailed decision tokens), `Opportunity` (venture dossier). Repository owns
  all SQL. *Deviation from ADR-0001:* `create_all` instead of Alembic until
  the schema stabilizes — logged deliberately; pre-1.0, single dev, SQLite.
- **Email HITL (ADR-0002)**: `notify.py` port + Console/Resend adapters; the
  graph pauses via `interrupt()` + AsyncSqliteSaver checkpointer
  (thread_id = run_id, survives restarts). Review links `/r/{token}/{decision}`
  are single-use, expiring, no-indexed; last decision auto-resumes the graph.
  Side effects (tokens, email) live in `request_review`, a node *before* the
  interrupt — on resume LangGraph re-executes the interrupted node from the
  top, so `human_gate` contains nothing but the interrupt call.
- **FastAPI service** (`p2pops-api`): POST/GET runs, run detail, SSE event
  stream, ideas, opportunities, stats, review action pages (on-brand HTML);
  optional bearer token on mutating endpoints; CORS for the web app.
- **Venture pipeline (ADR-0004)** (`src/p2pops/venture/`): on approval, each
  idea runs evidence → 4 parallel analysis agents → deterministic
  validation gate → architect (4-6 directions + rejected framings, cites
  curated founder-principle library) → deterministic weighted ranking w/
  saturation damping → red team (5 lenses) ⇄ refiner bounded loop → product
  vision → full `OpportunityDossier` persisted. LLMs produce artifacts;
  code makes decisions. Temperature 0, retries, clamping validators.
- **Tests: 23 passing** — repository, API (hermetic ASGI), scoring/gates,
  and three offline end-to-end venture-graph scenarios through the
  `_structured` seam (happy path w/ refinement, gate rejection, parking).
- **Live verification status (superseded, see Phase 1.5):** API booted;
  live run reached OpenRouter and failed with 402 — OpenRouter balance
  exhausted (~890 tokens affordable). Full live pass pending either a
  top-up or a different provider.

### Phase 1.5 — Groq provider, LLM-call resilience layer, first full live pass (2026-07-06)
- **Added Groq as a third LLM provider** (config.py, chat_model.py) since
  Anthropic direct ($0) and OpenRouter (~890 tokens) were both exhausted.
  User supplied a Groq key directly in chat — dropped straight into `.env`,
  not echoed back (standard handling for pasted secrets).
- **Five real bugs found and fixed via live iteration** (full detail in
  ADR-0005, `docs/adr/0005-llm-call-resilience-and-groq-model-choice.md`):
  1. Empty tool-result content (`fetch_article_text` returning `""`,
     `search_hacker_news` returning `[]`) produced a `ToolMessage` with zero
     MCP content blocks — Groq rejects this outright. Fixed at the source:
     both tools now return an explicit placeholder instead of empty output.
  2. `API_TOKEN=` (blank) in `.env` parsed as `""`, not `None` — silently
     locked out every API request. Fixed with a `field_validator` that
     normalizes blank env strings to `None` across every optional secret
     field (`_BLANKABLE_FIELDS` in config.py), not just this one.
  3. Two uncoordinated retry layers (OpenAI SDK's own + ours) stacked
     unpredictable waits. Fixed: `max_retries=0` on every chat model
     instance; `resilience.with_retry` is now the sole retry authority.
  4. A 413 "payload too large" reused 429's `rate_limit_exceeded` wording —
     status code must win over text, or a permanently-oversized request
     gets retried forever. A 400 `tool_use_failed`/`json_validate_failed`
     is the opposite case (stochastic model output, resampling helps) and
     needed its own explicit exception to the "4xx = stop" rule.
  5. `openai/gpt-oss-20b`'s Groq on-demand tier caps at 8,000 TPM,
     *org-wide, sliding window* — waiting between runs doesn't help, only
     shrinking work-per-run or a bigger-headroom model does. Queried this
     account's actual per-model rate limits and switched to
     `llama-4-scout-17b-16e-instruct` (30,000 TPM, verified live for both
     tool-calling and structured output) as the default-tier model.
- **New module `src/p2pops/resilience.py`** (`with_retry`, 9 direct unit
  tests): the single retry seam used by `llm.py`, both agents, and every
  venture agent call.
- **Research Agent hardened**: `MAX_SEARCH_RESULTS=6`, `MAX_ARTICLE_CHARS=1200`
  (mcp/server.py), `MAX_RESEARCH_STEPS=16` recursion ceiling, prompt now
  requires a real, non-null `source_url` traced to an actual search result
  for every reported idea.
- **First full live pass, same day, no mocks**: POST /api/v1/runs → Research
  Agent found 3 real problems → Analyst scored/shortlisted all 3 → email
  sent (console adapter, real HTML with signed links) → all 3 approved via
  `/r/{token}/approve` → graph resumed → venture pipeline ran for all 3 →
  **2 honestly parked** (unresolved critical stress-test issues after 2
  refinement rounds — the bounded-loop design working as intended, not a
  failure) → **1 complete**, full `OpportunityDossier` with a coherent
  product vision ("TrustLayer SDK" — plug-and-play CI/CD trust-evaluation
  SDK, positioned against named competitors, with a concrete 90-day
  execution plan and success metrics). Deterministic ranking scores and
  gate pass/fail history all inspectable in the persisted dossier JSON.
- **Tests: 37 passing** (was 23 at end of Phase 1).
- ADR-0005 added.

### Phase 0.5 — Brand + web foundation (2026-07-05)
- First git commits (repo had none): baseline of Milestones 1–3, then the web app.
- `web/`: Next.js 16 + TS + Tailwind v4 + motion, pnpm.
- Design system "obsidian & ember" in `web/src/app/globals.css`: ink/mist/maroon
  token scales, glass + ember-gloss + grain utilities, ticker/ember/rise
  keyframes, Inter + Instrument Serif + JetBrains Mono via next/font.
- Landing page: nav with discreet Console pill, CSS-animated hero with live
  discovery ticker (real Research Agent output), Showcase (3 real validated
  problems w/ scores), Method (5-stage agent production line), pipeline
  stats, footer.
- `/console`: operations console shell — module grid (Orchestration, Runs,
  Guardrails, Human gate, Tracing, Evaluations) with live/wiring status,
  no-index metadata.
- ADRs 0001–0003 (repo structure + frontend reversal, email HITL with signed
  links, above-fold CSS animation rule).
- Verified: `pnpm build` clean, `pnpm lint` clean, headless-browser
  screenshots of hero + console, all sections present in SSR HTML.

## Goal

P2POps: a LangGraph-orchestrated multi-agent system (Research, Analyst, PM,
Architect, Engineer, QA agents under a Supervisor) that discovers AI-related
problems from HN/Reddit, filters them with guardrails, pauses for human review
every N days (configurable, on-demand for demos), and on approval generates a
PRD + architecture doc + code scaffold. Built as a recruiter-facing portfolio
project demonstrating a production-shaped 2026 AI engineering stack.

## Approved Plan Summary

Milestones:
1. Bootstrap — repo, uv, config, LiteLLM + LangSmith + Logfire, one traced call. **(done)**
2. Research Agent — HN + Reddit + BS4 tools exposed via an MCP server; agent reasons over them. **(done, HN-only)**
3. Supervisor + Analyst — guardrailed scoring/dedupe (NeMo Guardrails + ChromaDB), shortlist in SQLite. **(done)**
4. HITL gate + Streamlit — LangGraph `interrupt()`/checkpointer, accept/reject dashboard. **(next)**
5. Build squad subgraph — PM -> Architect -> Engineer fan-out -> QA reflection loop (RAG over past PRDs).
6. AgentOps console — per-agent cost/latency/token metrics in the dashboard.
7. Evals & CI — Braintrust evals per agent, Promptfoo prompt regression, GitHub Actions.
7.5. FastAPI service layer + Docker Compose (added after 2026 JD gap analysis).
8. Polish — README/org-chart diagram, demo script, screenshots.

## Known Knowns

- Stack: LangGraph, MCP, ChromaDB (RAG), NeMo Guardrails, LiteLLM, LangSmith,
  Logfire, Braintrust, Promptfoo, Streamlit, FastAPI, Beautiful Soup, PRAW.
- Models via LiteLLM: `anthropic/claude-haiku-4-5-20251001` for high-volume
  agent work, `anthropic/claude-sonnet-5` for the PM/Architect/build agents.
- Tool overlap resolved by giving each observability tool a distinct job:
  LangSmith = live LLM traces, Logfire = app/pipeline telemetry, Braintrust =
  offline eval datasets, Promptfoo = CI prompt regression.

## Known Unknowns

- Direct `ANTHROPIC_API_KEY` still has no credit balance (confirmed via two
  live 400 errors). Not currently blocking anything -- `LLM_PROVIDER` is set
  to `openrouter`, which has working credits, so both entrypoints run live.
  Switching back to `anthropic` direct is a one-line `.env` change once that
  account is funded.
- Reddit app registration (reddit.com/prefs/apps) can be rejected/delayed —
  HN (Algolia API, no auth) is the primary source specifically so Milestone 2
  isn't blocked on it. Deferred by user choice; HN-only for now.

## Unknown Knowns Surfaced

- Reddit deprecated unauthenticated `.json` scraping in May 2026 — original
  "Beautiful Soup scrapes Reddit" idea would have been both ToS-broken and
  fragile. Re-scoped: PRAW (OAuth) for Reddit, BS4 for enriching linked
  external articles instead.
- 2026 JDs weight eval literacy and RAG/vector-DB experience heavily — original
  stack had strong evals but no RAG; added ChromaDB with an honest job (semantic
  dedupe + PRD retrieval), not a bolted-on chatbot.

## Unknown Unknowns Discovered

- NeMo Guardrails' Python/Pydantic-v2/LangGraph compatibility was a real risk
  going in; verified fine (supports 3.10-3.13, Pydantic >=2.5, official
  LangGraph integration) — not re-litigated further.
- NeMo Guardrails 0.23's LLM integration API is different from the
  older "pass a LangChain LLM straight in" pattern I half-remembered --
  it now wants an `LLMModel` protocol object, satisfied via
  `nemoguardrails.integrations.langchain.llm_adapter.LangChainLLMAdapter`
  wrapping our own `get_chat_model()`. Verified empirically (small standalone
  script) before wiring into `guardrails.py`, including how to read the
  allow/block verdict as a clean boolean (`GenerationOptions(rails=["input"],
  output_vars=["allowed"])` -> `result.output_data["allowed"]`) rather than
  string-matching the refusal message.
- Anthropic's structured-output/tool-schema validation (reached via
  OpenRouter -> Bedrock in this case) rejects a JSON schema with
  `minimum`/`maximum` on an integer field -- pydantic's `Field(ge=0, le=100)`
  on `IdeaVerdict.score` caused a live 400 on the very first Analyst call.
  Fixed by dropping the constraint from the schema and clamping at runtime
  with a `field_validator` instead (see Decisions).

## Decisions Made

| Decision | Reason | Risk | Reversible? |
|---|---|---|---|
| Python 3.13, managed by `uv` | Already installed locally; within NeMo Guardrails' supported range (3.10-3.13) | Low | Yes |
| `src/p2pops` package layout via `uv init --package` | Standard, importable, keeps CLI entry point (`p2pops`) trivial | Low | Yes |
| Logfire configured with `send_to_logfire="if-token-present"` | Lets the app run fully offline with no token during dev/demo prep | Low | Yes |
| Anthropic models addressed as `anthropic/<model>` in LiteLLM | Forces the Anthropic provider explicitly rather than relying on LiteLLM's model registry recognizing new 2026 model IDs | Low | Yes |
| Bootstrap CLI no-ops the LLM call (with a clear message) when `ANTHROPIC_API_KEY` is unset | Lets Milestone 1 be fully verified structurally without live secrets | Low | Yes |
| Research Agent's chat model comes from a new `chat_model.get_chat_model()` factory (`langchain-anthropic` or `langchain-openai`, provider-switched), not the LiteLLM wrapper in `llm.py` | LangGraph's `create_react_agent` needs native tool-calling/binding; LiteLLM's LangChain shim doesn't reliably support that yet. `llm.py` stays the path for simple, non-agentic completions (e.g. bootstrap check, later scoring calls) | Low | Yes — can collapse to one path once LiteLLM's LangChain tool-calling support matures |
| Research Agent's tools are served over a real MCP server (`p2pops.mcp.server`, stdio transport) rather than plain LangChain `@tool` functions | This is the actual point of using MCP for the portfolio story — tools are portable to any MCP client, not just this agent | Low | Reversible but would defeat the purpose |
| Beautiful Soup used only for reading external article links found via HN/Reddit, not for scraping Reddit itself | Reddit deprecated unauthenticated `.json` scraping in 2026; scraping Reddit HTML would violate ToS and break easily | Low | N/A — this was corrected before any code was written |
| Added `LLM_PROVIDER` (`anthropic` \| `openrouter`) to `Settings`, with parallel `anthropic_*`/`openrouter_*` model fields and `active_api_key`/`default_model`/`builder_model` properties that resolve based on it | User supplied a working OpenRouter key while the direct Anthropic account had no credits; this is also the honest demonstration of LiteLLM's actual selling point (provider swap = config change, not a rewrite) | Low | Yes |
| `complete()` and `get_chat_model()` both pass an explicit `max_tokens` cap (1024 / 2048) instead of relying on provider defaults | OpenRouter rejected the very first live request with a 402 because the model's uncapped default max output (64k tokens) cost more than the account could afford | Low | Yes |
| Analyst Agent is a plain async pipeline function (guardrail -> dedupe -> structured scoring call -> persist), not a LangGraph tool-calling agent like Research | This is the honest shape for what the Analyst actually does -- a fixed sequence of checks per idea, not open-ended tool use. It's still a distinct node in the Supervisor graph and every step is traced | Low | Yes, could become a `create_react_agent` later if it needs to dynamically decide what to check |
| NeMo Guardrails' own LLM call goes through `get_chat_model()` (via `LangChainLLMAdapter`), not a separately configured NeMo "engine" | Keeps guardrails honoring whichever `LLM_PROVIDER` is active, instead of hardcoding a second, disconnected provider config just for the rails | Low | Yes |
| Guardrails config (`config.yml`/`prompts.yml`) is inlined as a Python string in `guardrails.py` via `RailsConfig.from_content()`, not a `config/` directory of YAML files | Small, single-purpose rail (one input flow); a full config directory is the right call once output rails or more flows are added | Low | Yes -- trivial to split into files later |
| `IdeaVerdict.score` has no `ge=0, le=100` pydantic constraint; clamped at runtime via `field_validator` instead | Anthropic (via OpenRouter/Bedrock) rejects a structured-output schema with `minimum`/`maximum` on an integer field -- this was a real live 400 on the first Analyst call, not a hypothetical | Low | Yes |
| Chroma's default local embedding function (all-MiniLM-L6-v2, ONNX) is used for dedupe, with `hnsw:space: cosine` and a distance threshold of 0.3 | No extra API key/cost; empirically verified cosine distance separates near-duplicate problem statements (~0.05-0.15) from unrelated ones (~0.9+), so 0.3 has real margin on both sides | Low | Yes, threshold is one constant (`memory.DUPLICATE_DISTANCE_THRESHOLD`) |
| Shortlist threshold (`analyst.SHORTLIST_THRESHOLD = 50`) is a plain module constant, not user-configurable yet | No indication yet of what the right knob is; premature to push it into `Settings` before Milestone 4's HITL dashboard needs to expose/tune it | Low | Yes |
| `self_check_input` prompt sets `max_tokens: 50` and asks for a one-word Yes/No answer, instead of NeMo's own default (1024) | The OpenRouter account's credit balance dropped low enough during this session's demo runs that a live test failed with a 402 ("requested up to 1024 tokens, can only afford 933"). A yes/no classification never needed 1024 tokens anyway -- this is a real cost fix, not just a workaround for a temporarily low balance | Low | Yes |

## Deviations

| Original plan | Deviation | Reason | Impact |
|---|---|---|---|
| None yet | — | — | — |

## Files Changed

### Milestone 1
- `pyproject.toml` — project metadata, deps (litellm, langsmith, logfire, pydantic-settings, python-dotenv; pytest as dev dep)
- `src/p2pops/config.py` — `Settings` (pydantic-settings), `get_settings()`
- `src/p2pops/telemetry.py` — `configure_telemetry()` wiring LangSmith env vars + Logfire
- `src/p2pops/llm.py` — `complete()`, a traced LiteLLM wrapper tagged per-agent
- `src/p2pops/main.py` — bootstrap check CLI
- `src/p2pops/__init__.py` — exposes `main` for the `p2pops` console script
- `tests/test_config.py` — settings defaults load without a `.env` file
- `.env.example`, `.gitignore`, `README.md` — new

### Milestone 2
- `src/p2pops/tools/hn.py` — `search_hn()`, keyless HN Algolia search, returns `HNStory` pydantic models
- `src/p2pops/tools/web.py` — `fetch_article_text()`, BeautifulSoup-based article text extraction
- `src/p2pops/mcp/server.py` — FastMCP server exposing `search_hacker_news` / `read_article` over stdio
- `src/p2pops/agents/research.py` — Research Agent: `create_react_agent` (LangGraph), tools loaded from the MCP server via `langchain-mcp-adapters`
- `tests/test_hn_tool.py` — live test against the real HN Algolia API
- `tests/test_mcp_server.py` — spins up the MCP server as a subprocess, asserts both tools are exposed
- `pyproject.toml` — added `mcp`, `httpx`, `beautifulsoup4`, `langgraph`, `langchain-anthropic`, `langchain-mcp-adapters`; dev: `pytest-asyncio`; new console scripts `p2pops-research`, `p2pops-mcp-server`; `[tool.pytest.ini_options] asyncio_mode = "auto"`

### OpenRouter provider swap (same session, after user supplied an OpenRouter key)
- `src/p2pops/config.py` — added `llm_provider`, `openrouter_api_key`, `openrouter_default_model`, `openrouter_builder_model`; `default_model`/`builder_model`/`active_api_key` are now properties that resolve per-provider
- `src/p2pops/chat_model.py` — new: `get_chat_model()` factory, returns `ChatOpenAI` (pointed at OpenRouter's base URL) or `ChatAnthropic` depending on `llm_provider`; both capped with `max_tokens`
- `src/p2pops/llm.py` — `complete()` now uses `settings.active_api_key` and passes an explicit `max_tokens` (default 1024)
- `src/p2pops/agents/research.py`, `src/p2pops/main.py` — no-key guards now check `settings.active_api_key` and report the active provider by name
- `pyproject.toml` — added `langchain-openai`
- `.env` / `.env.example` — added `LLM_PROVIDER`, `OPENROUTER_API_KEY`
- `tests/test_config.py` — added a test asserting the OpenRouter provider switch resolves the right model strings and key

### Milestone 3
- `src/p2pops/models.py` — new: `DiscoveredIdea`, `ResearchReport`, `IdeaVerdict` (with clamping validator), `AnalyzedIdea`
- `src/p2pops/agents/research.py` — now passes `response_format=ResearchReport` to `create_react_agent`; `run_research()` returns a structured `ResearchReport`, not a text blob; CLI prints from the structured ideas
- `src/p2pops/guardrails.py` — new: NeMo Guardrails input rail (`self check input` flow) with a domain-specific prompt, `is_idea_allowed(text) -> bool`
- `src/p2pops/memory.py` — new: ChromaDB-backed semantic dedupe, `find_duplicate()` / `remember()`
- `src/p2pops/store.py` — new: SQLite persistence, `save_idea()` / `list_ideas()`
- `src/p2pops/agents/analyst.py` — new: Analyst Agent -- guardrail check -> dedupe check -> structured scoring call -> persist, per idea
- `src/p2pops/graph.py` — new: Supervisor `StateGraph` (research -> supervisor -> conditional route -> analyst -> END)
- `src/p2pops/pipeline.py` — new: `p2pops-pipeline` CLI, runs the full graph once and prints the shortlist
- `src/p2pops/telemetry.py` — `configure_telemetry()` now reconfigures stdout to UTF-8 (LLM output routinely contains em-dashes etc. that mangled on Windows' default console codepage)
- `tests/test_memory.py`, `tests/test_store.py`, `tests/test_guardrails.py` — new; memory/store are deterministic and local, guardrails is a live LLM test (blocks spam, allows a real problem statement)
- `pyproject.toml` — added `nemoguardrails`, `chromadb`; new console script `p2pops-pipeline`

## Verification

| Check | Result | Notes |
|---|---|---|
| `uv run pytest` | Pass (7/7) | Config, HN, MCP tool listing, memory dedupe, SQLite store, live guardrails allow/block |
| `uv run p2pops-pipeline "AI agent evaluation and observability tools"` (live) | **Pass — real end-to-end run** | 8 ideas discovered, all passed guardrails, 7 shortlisted (scores 72-87) with real reasoning, 1 rejected below threshold, all persisted to SQLite |
| `uv run p2pops-pipeline "AI code review automation"` (live, second topic) | **Pass** | Confirms the pipeline isn't a one-shot fluke; 4 ideas, 3 shortlisted, 1 rejected |
| SQLite persistence | **Pass** | 12 rows across both runs confirmed via direct `list_ideas()` query |
| Direct Anthropic path | Untested live (no credits on that account) | Unchanged from Milestone 2's note; still exercised by unit tests |
| `uv run pytest` (full suite, after cost fix) | Pass (7/7) | Re-ran after the guardrails `max_tokens` fix, confirming it works even with the now-lower OpenRouter balance |

## Open Questions

- Reddit app registration (reddit.com/prefs/apps, "script" type) — deferred by
  choice; HN-only for Milestone 2 and onward until you want to add it.
- OpenRouter account balance is now low after this session's live demo runs
  (hit a 402 once, fixed the root inefficiency, but the account isn't
  bottomless) — may be worth topping up before the next milestone's live runs.
- Shortlist threshold (currently a hardcoded 50) and the guardrails prompt's
  bar for "legitimate problem" haven't been tuned against real user judgment
  yet -- worth revisiting once the HITL dashboard (Milestone 4) lets you see
  disagreements between the Analyst's calls and your own accept/reject.

## Follow-ups

- Milestone 4: HITL gate + Streamlit -- LangGraph `interrupt()`/checkpointer,
  accept/reject dashboard reading from the SQLite store built this session.
- Note for the recruiter-facing README/demo script (Milestone 8): call out
  the provider swap (`LLM_PROVIDER=anthropic` <-> `openrouter`) explicitly as
  a live demonstration of LiteLLM's routing value, and the guardrails ->
  dedupe -> score pipeline as the AgentOps/evaluation story.
