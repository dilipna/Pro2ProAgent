"""LLM cost estimation — USD per token, keyed by (provider, model).

Rates are per-1M-tokens list prices, captured 2026-07 from each provider's
public pricing page for the specific models this project actually calls
(`config.py`'s `*_default_model`/`*_builder_model`). This is an *estimate*
against list price, not a reconciliation against a real invoice — provider
pricing changes over time and volume/promotional discounts aren't reflected.
Good enough for relative cost comparison across agents/models (the actual
LLMOps use case here), not for finance-grade billing.

An unrecognized (provider, model) pair returns 0.0 rather than raising —
cost estimation is observability, and a missing price should never be the
reason an agent call fails.
"""

from dataclasses import dataclass

# USD per 1,000,000 tokens: (input_rate, output_rate).
_RATES_PER_MILLION: dict[tuple[str, str], tuple[float, float]] = {
    # Groq — https://groq.com/pricing (on-demand tier), captured 2026-07.
    ("groq", "meta-llama/llama-4-scout-17b-16e-instruct"): (0.11, 0.34),
    ("groq", "openai/gpt-oss-120b"): (0.15, 0.75),
    ("groq", "openai/gpt-oss-20b"): (0.10, 0.50),
    ("groq", "llama-3.3-70b-versatile"): (0.59, 0.79),
    ("groq", "llama-3.1-8b-instant"): (0.05, 0.08),
    ("groq", "qwen/qwen3-32b"): (0.29, 0.59),
    # Anthropic direct — https://www.anthropic.com/pricing, captured 2026-07.
    ("anthropic", "claude-haiku-4-5-20251001"): (1.00, 5.00),
    ("anthropic", "claude-sonnet-5"): (3.00, 15.00),
    # OpenRouter — pass-through pricing approximating the underlying
    # Anthropic model; OpenRouter's own small per-request margin is ignored.
    ("openrouter", "anthropic/claude-haiku-4.5"): (1.00, 5.00),
    ("openrouter", "anthropic/claude-sonnet-4.5"): (3.00, 15.00),
}


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def estimate_cost_usd(provider: str, model: str, usage: Usage) -> float:
    rates = _RATES_PER_MILLION.get((provider, model))
    if rates is None:
        return 0.0
    input_rate, output_rate = rates
    return (usage.input_tokens * input_rate + usage.output_tokens * output_rate) / 1_000_000


def extract_usage(raw_message: object) -> Usage | None:
    """Pulls token counts from a LangChain `AIMessage`'s `usage_metadata`
    (the standard shape across providers: `input_tokens`/`output_tokens`/
    `total_tokens`). Returns None if the message carries no usage data —
    happens if a provider integration doesn't populate it; callers must
    treat that as "unknown," not "zero."
    """
    usage = getattr(raw_message, "usage_metadata", None)
    if not usage:
        return None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if input_tokens is None or output_tokens is None:
        return None
    return Usage(input_tokens=int(input_tokens), output_tokens=int(output_tokens))
