# ADR-0009: LLM cost tracking

**Date:** 2026-07-07 · **Status:** Accepted

## Context

The original stack ambition (`PROJECT_BRAIN.md` §7) named "LLM Analytics:
model usage, provider, tokens, cost" as a console capability; through Phase
3, none of that existed — no per-call token capture anywhere in the
codebase. Every `.with_structured_output(schema)` call discards the raw
`AIMessage` (and its `usage_metadata`) the moment it parses the structured
result, so there was nothing to record from even if a ledger existed.

## Decision

### A global ledger, not a run-scoped one

`LlmCall` (new table: `agent`, `provider`, `model`, `input_tokens`,
`output_tokens`, `estimated_cost_usd`, `created_at`) has no foreign key to
`runs`. Threading `run_id` through every call site — all ten venture/build
agent functions, the Analyst's scorer, and the Research Agent's multi-turn
ReAct loop — for this feature alone was judged not worth the invasiveness
against the value gained (a "cost for this specific run" drill-down). The
console's cost panel answers "where does spend go, by agent and by model,"
which is the actual LLMOps question this feature exists to answer. Per-run
attribution is a documented, honest scope boundary — not a hidden gap — and
a natural extension if it's ever needed (adding an optional `run_id` column
and passing it down `_structured`'s call chain).

### One capture seam, reused by every call site

`cost_tracking.record_usage(agent, tier, raw_message)` (new module) is the
single place token counts turn into a persisted, priced row. Three call
sites feed it:

- `venture/agents.py::_structured` — covers all ten venture *and* build
  agents in one place, since `build/agents.py` already calls through this
  exact function (module-attribute access, per ADR-0006).
- `agents/analyst.py`'s `score()` closure.
- `agents/research.py::run_research` — different shape: a ReAct loop makes
  one LLM call per tool-calling turn, so usage is recorded once per message
  in the final trajectory rather than once per top-level call, yielding one
  `LlmCall` row per actual model turn instead of a single misleading
  aggregate.

`record_usage` is deliberately best-effort: a DB failure while recording
cost is logged and swallowed, never propagated — cost tracking is
observability, and it must never be the reason an agent call fails. This
mirrors how `RunEvent` logging is treated as non-blocking observability
elsewhere in the codebase, not a new pattern invented for this feature.

### `include_raw=True`, with an explicit trap defused

Getting at `usage_metadata` requires `.with_structured_output(schema,
include_raw=True)` instead of the bare call — the raw `AIMessage` isn't
otherwise reachable. This is not a free change: with `include_raw=True`,
LangChain stops raising on a malformed/unparseable response and instead
returns `{"raw": ..., "parsed": None, "parsing_error": <exception>}`. Left
unhandled, this would have **silently regressed** the retry-on-malformed-
output behavior ADR-0005 spent five live-debugged fixes establishing
(`with_retry`'s `_is_retryable` classifies Groq's `tool_use_failed`/
`json_validate_failed` 400s as retryable specifically because they're
stochastic generation failures, not structural ones). Both call sites
(`_structured`, `analyst.score`) now explicitly re-raise when
`parsing_error` is set or `parsed` is `None`, before `with_retry` ever sees
a return value — preserving the exact existing retry contract. This was
caught during design, not live in production, precisely because the ADR-0005
incident history made the risk visible in advance.

### Pricing is an estimate against list price, not a bill reconciliation

`pricing.py`'s rate table (USD per 1M tokens, keyed by `(provider, model)`)
is hand-captured from each provider's public pricing page for the specific
models `config.py` actually selects, dated in the module docstring. An
unrecognized `(provider, model)` pair returns `$0.00` rather than raising —
a missing price must never be the reason an agent call fails, and a
console showing "$0.00 (unpriced)" is more honest than a stack trace.
Volume discounts, promotional credits, and provider price changes are not
reflected; the module docstring says so explicitly.

## Alternatives considered

- **Wrap `get_chat_model()` itself to auto-capture usage on every call.**
  Rejected: `get_chat_model()` returns a bindable LangChain model object
  used inside LangGraph's `create_react_agent` (Research) as well as direct
  `.with_structured_output()` calls (venture/build/analyst) — there is no
  single post-call hook at that layer that sees every response uniformly
  across both usage patterns. Capturing at each call site's own natural
  seam (`_structured`, `score`, the ReAct result's message list) is more
  code but strictly more correct.
- **A `run_id`-scoped ledger from day one.** Rejected for this phase — see
  "global ledger" above. Revisit if a per-run cost breakdown becomes a real
  product requirement rather than a nice-to-have.
- **LLM-as-judge or third-party cost-tracking SaaS (e.g., a LangSmith-native
  cost view).** LangSmith does track token usage per traced run already
  (Phase 3 verified this live), but it's not exposed as an aggregate
  console panel without either a paid LangSmith plan's analytics or
  building the same aggregation this ADR describes — so a first-party
  ledger was the more portable, zero-additional-cost choice, and doesn't
  preclude also reading LangSmith's own numbers later.

## Consequences

- `chat_model.py` gained a `resolve_model(tier) -> (provider, model)` helper,
  factored out of `get_chat_model()`'s existing branching so
  `cost_tracking.py` attributes usage to the exact model id actually called
  without duplicating (and risking drift from) that logic.
- New tests: `test_pricing.py` (pure functions, no DB/LLM), plus
  `test_repository.py::test_cost_summary_*` (aggregation math, hermetic).
  The wiring itself (real `AIMessage.usage_metadata` extraction end-to-end)
  was live-verified during this session against the funded Groq key —
  `analyze_idea` recorded a real 288/62-token call, `validate_problem`
  recorded a real 477-token call, and `cost_summary()` aggregated both
  correctly — rather than trusted on unit tests alone, per this project's
  standing "live-verify, don't just wire" practice.
- The console's Evaluations module status changed from "wiring" to "live"
  in the same pass, since Promptfoo (ADR-0008) closed that gap concurrently
  with this one.
