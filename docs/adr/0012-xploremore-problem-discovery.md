# ADR-0012: XploreMore as the primary problem-discovery source

**Date:** 2026-09-15 · **Status:** Accepted

## Context

The Research Agent discovered problems by searching Hacker News stories
(Algolia, `tags=story`) and the web (DuckDuckGo), then asking the model to
pick "problems people complain about" out of headlines. Headlines are mostly
announcements; the evidence for a problem lives in discussions. Each run also
re-derived demand from scratch: the Analyst had to *guess* "how many people
likely share it".

XploreMore (a separate repo and system, no LLM in its serving path) ingests
Hacker News (Ask HN plus comments), GitHub issues, Lobsters and Stack Exchange
discussions. It classifies pain points, clusters duplicates into problems
and ranks them by demand (distinct voices, sources, recency, engagement). It
serves `GET /v1/problems` and `GET /v1/problems/{id}` behind API keys and a
Redis rate limit, with an OpenAPI contract
(`contracts/xploremore/problems.v1.openapi.json`, vendored here).

## Decisions

### 1. Two new research tools, same function for both transports

`tools/xploremore.py` defines `find_problems` and `get_problem`. They are
bound in-process in `agents/research.py` (the production transport,
ADR-0011) and registered as `@mcp.tool()` in `mcp/server.py`. Both
transports call the same coroutine, so they can't drift.

### 2. Discovery never depends on XploreMore being up, and code (not the model) decides the fallback

- **Timeout:** 5 s per request (`XPLOREMORE_TIMEOUT_S`).
- **Circuit breaker:** 3 consecutive failures open it for 60 s. Failures are
  timeouts, connection errors, 5xx, 401/403 and unparseable payloads. After
  the window, one trial call closes it or re-opens it. 404 and 422 mean the
  service answered, so they are not failures.
- **429:** holds the breaker open for `Retry-After` (seconds or HTTP-date,
  capped at 1 h) without counting as a failure. Being over quota is not an
  outage, but we must not keep hammering.
- **Before building the agent**, `availability()` returns `not_configured`
  (no `XPLOREMORE_API_URL`), `circuit_open` or `ok`. Only `ok` binds the
  XploreMore tools and the XploreMore prompt. Otherwise the agent gets
  exactly the pre-existing HN/web toolset and prompt. The fallback is a code
  path, not an instruction the model may ignore.
- **Mid-run failure:** the tool returns an explicit, non-empty
  `{"unavailable": reason, "fallback": "Use search_hacker_news and search_web instead."}`.
  An empty tool result breaks Groq (see `mcp/server.py`).
- **Over MCP**, calls run in the server subprocess with its own breaker. The
  parent mirrors observed outages into its breaker, so the next run's
  availability check sees them.

### 3. Prompt: XploreMore first, HN/web to validate or fill gaps

The XploreMore prompt budgets `find_problems` once, `get_problem` at most
once, `search_hacker_news` once, `search_web` only for gaps, and
`read_article` once. The step ceiling rises from 18 to 22 only when these
tools are bound: two more sanctioned tool calls means four super-steps.

### 4. Provenance is attached by code from what the agent actually received

`DiscoveredIdea` gains `problem_id`, which the model may fill. It also gains
`provenance`, which is hidden from the model's response schema via
`SkipJsonSchema`. After the turn, `observe_tool_messages` reads the
`find_problems`/`get_problem` tool results from the conversation, which works
the same for both transports. `attach_provenance` then:

- keeps the model's `problem_id` only if that problem was really returned;
- otherwise links an idea whose `source_url` is an evidence URL of exactly
  one returned problem;
- drops invented ids and overwrites any provenance the model tried to supply.

A card saying "23 people" must trace back to a real API response.

Provenance (problem id, voices, sources, platforms, demand, up to 5 evidence
URLs) flows through the rest of the pipeline:

- **Dedupe:** an idea for an XploreMore problem already in memory is a
  duplicate by identity, checked before the semantic Chroma check. Chroma
  metadata `xploremore_problem_id` records it.
- **Analyst:** the scoring prompt gets one extra line: "Measured demand
  (counted by XploreMore from public posts, not estimated): N distinct
  people across M sources (platforms)". Ideas without provenance get the
  byte-identical original prompt, so the promptfoo scenarios are unaffected.
- **Persistence:** `ideas.xploremore_problem_id` and `ideas.provenance`
  (JSON snapshot at discovery) are additive columns via
  `_ADDITIVE_COLUMNS`.
- **API and web:** `IdeaOut` / `ShowcaseItemOut.provenance` includes a
  server-computed `card_line`. The showcase card and story page show
  "Discovered via XploreMore: N people across M sources" plus the evidence
  links. The field is optional in the web types, so an older API still
  renders.

### 5. Token budget

Results are compact: a statement of at most 240 characters, 2 evidence
excerpts of at most 200 characters each, rounded demand, no engagement
blobs. This mirrors XploreMore's own MCP server. Groq's remaining chat models
on this account are all 8,000 TPM (re-measured 2026-09-15). The worst case,
3 problems with every field at its cap, is about 3.1k characters, and a test
bounds it. If no multi-voice problem matches a topic, the client retries once
with `min_voices=1` and says so in a `note`, rather than returning nothing.

### 6. Research retries per model call, not per turn

This was found during this ADR's live end-to-end run, and it affects both
discovery sources. On the 8,000 TPM tier, `with_retry` around the whole ReAct
turn re-spent every earlier step's tokens on each retry and never
converged: `research failed after 4 attempt(s)`, "Used 7547, Requested 2174".
The research agent now opts in to `get_chat_model(retry_calls_as=...)`,
which retries only the call that hit the 429, still through
`resilience.with_retry`. The whole-turn retry is kept at 2 attempts, and
`research_turn_timeout_s` is 240 s (was 90). The same run then completed:
230 s of research with 11 per-call waits.

## Consumer contract test

`tests/test_xploremore.py` mocks XploreMore with `httpx.MockTransport`. It
validates every mocked payload against the vendored contract's component
schemas, and every outgoing query string against its parameter schemas. The
latter catches the client sending, say, `limit=50` where the contract allows
25. XploreMore has the provider-side drift test. To update the copy, see
`contracts/xploremore/README.md`.

## Consequences

- Set `XPLOREMORE_API_URL` and `XPLOREMORE_API_KEY` (Render env) to enable.
  Unset, behaviour is exactly what it was before this ADR.
- Discovery quality is now partly XploreMore's classifier and clustering
  quality, which XploreMore documents as provisional. Its labels are
  assistant-made and not human-audited, and precision outside GitHub issues
  is low. HN/web validation in the prompt is the mitigation. Whether this
  source is actually better is an experiment (XploreMore's P6 A/B), not an
  assumption.
- The breaker is per process, which is fine for the single-replica API
  (ADR-0007). Multiple replicas would each learn an outage independently.
