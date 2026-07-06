# ADR-0005: Rate-limit-aware retry layer, and Groq model selection by measured headroom

**Date:** 2026-07-06 · **Status:** Accepted

## Context

Live verification of the full run → email gate → approve → venture pipeline
chain (ADR-0004) surfaced five distinct real failures against Groq's free
tier, in order:

1. **Empty tool-result content.** `fetch_article_text` could return `""` on
   a page with no extractable text; `search_hacker_news` returned `[]` on
   zero HN matches. `langchain-mcp-adapters` maps MCP content blocks
   one-to-one from the return value, so both became a `ToolMessage` with
   **zero** content blocks — which Groq's chat-completions endpoint rejects
   outright (`content: minimum number of items is 1`). Not a rate limit,
   not transient: a real bug in two tool implementations.
2. **Two independent, uncoordinated retry layers.** The OpenAI SDK's own
   client-level retry (default `max_retries`) was retrying 429s silently
   underneath our code, burning minutes of backoff before our own retry
   logic ever got a chance to reason about the error.
3. **413 "payload too large" reusing 429 wording.** Groq's response body
   for "this single request permanently exceeds the model's tokens-per-
   minute ceiling" uses the same `rate_limit_exceeded` code as a genuine,
   transient 429. Text matching alone cannot tell these apart — and
   retrying the first case can never succeed, no matter how long you wait.
4. **A hard step ceiling needs real headroom.** `create_react_agent` with
   `response_format` requires the mandatory-minimum happy path (one search,
   one read, the model's answer, then a forced `generate_structured_response`
   step) plus slack for a smaller model not perfectly obeying "call search
   exactly once" — it made 4 tool calls in one observed run.
5. **Model-choice-as-capacity-planning.** `openai/gpt-oss-20b` on Groq's
   on-demand tier has an **8,000 tokens/minute** cap, shared org-wide, on a
   **sliding** window — so spacing requests out does not help; only
   shrinking the total work per run or picking a model with more headroom
   does.

## Decision

**A single retry seam (`resilience.with_retry`)** used everywhere a real
LLM call happens (`llm.py`, Research/Analyst agents, all venture agents).
It classifies failures by authoritative signal, not vibes:

- HTTP status code wins whenever known: `429` → wait (provider-supplied
  `retry-after` hint or message-parsed wait time, honored exactly); any
  other 4xx → fail fast, no retry.
- Two named exceptions to the "other 4xx = stop" rule, because the
  *specific* error code says the failure is stochastic, not structural:
  `tool_use_failed` / `json_validate_failed` (the model's own sampling
  produced malformed output; resampling on retry routinely fixes it).
- `GraphRecursionError` is never retried (deterministic — the same
  conversation hits the same ceiling every time).
- `max_retries=0` set on every `ChatOpenAI`/`ChatAnthropic` instance in
  `chat_model.py`, so our layer is the only one making retry decisions.

**Tool outputs never return empty content** (`tools/web.py`,
`mcp/server.py`): a genuinely empty extraction or zero search results
becomes an explicit one-item placeholder, not a bare `""` / `[]`.

**Research Agent is explicitly budgeted**, not just capped defensively:
`MAX_SEARCH_RESULTS=6`, `MAX_ARTICLE_CHARS=1200` (mcp/server.py),
`MAX_RESEARCH_STEPS=16` (agents/research.py, sized against the measured
mandatory-minimum path plus real small-model variance), and the system
prompt explicitly forbids reporting an idea without a real `source_url`
traceable to a specific search result.

**Groq model chosen by measured rate limit, not assumed capability.**
Queried this account's actual per-model `x-ratelimit-limit-tokens` before
choosing:

| Model | TPM |
|---|---|
| llama-3.1-8b-instant | 6,000 |
| qwen/qwen3-32b | 6,000 |
| openai/gpt-oss-20b | 8,000 |
| openai/gpt-oss-120b | 8,000 |
| llama-3.3-70b-versatile | 12,000 |
| **llama-4-scout-17b-16e-instruct** | **30,000** |

`groq_default_model` (high-volume agent work: Research, Analyst, the four
parallel venture analysis agents) is now `llama-4-scout-17b-16e-instruct`
— verified live for both tool-calling (`bind_tools`) and structured output
(`with_structured_output`) before switching. `groq_builder_model` stays
`openai/gpt-oss-120b` (architect/red-team/refiner/strategist: lower call
volume, reasoning quality matters more than throughput).

## Consequences

- This is the actual, demonstrable AgentOps story: a naive integration
  fails constantly against real rate limits; the fixes here are the
  difference between a demo that "mostly works" and one that is provably
  reliable, with the reasoning for every retry/no-retry decision written
  down and unit-tested (`tests/test_resilience.py`, 9 tests covering every
  classification branch above).
- Verified end-to-end, live, same day: run → 3 ideas shortlisted → emailed
  → all 3 approved → venture pipeline executed for all 3 → 2 honestly
  parked (unresolved critical stress-test issues after 2 refinement
  rounds), 1 reached a complete `OpportunityDossier` with a coherent
  product vision ("TrustLayer SDK"). See `implementation-notes.md`.
- `llm.py`'s `complete()` (bootstrap check only, not on the pipeline's
  critical path) was deliberately left without this retry layer — single
  caller, low stakes, not worth the complexity yet.
