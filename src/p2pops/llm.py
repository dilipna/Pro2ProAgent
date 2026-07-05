"""Thin, traced wrapper around LiteLLM so every agent call is uniformly observable."""

import logfire
import litellm

from .config import get_settings


def complete(
    prompt: str,
    *,
    model: str | None = None,
    agent: str = "unknown",
    max_tokens: int = 1024,
) -> str:
    """Send a single-turn completion through LiteLLM, traced as a Logfire span.

    `agent` identifies which agent made the call, so per-agent cost/latency
    can be broken out in the observability dashboard later. `max_tokens`
    defaults conservatively -- some providers (OpenRouter free/low-credit
    accounts) reject a request outright if the model's uncapped default
    output length costs more than the account can afford.
    """
    settings = get_settings()
    resolved_model = model or settings.default_model

    with logfire.span("llm.completion", agent=agent, model=resolved_model):
        response = litellm.completion(
            model=resolved_model,
            messages=[{"role": "user", "content": prompt}],
            api_key=settings.active_api_key,
            max_tokens=max_tokens,
            metadata={"agent": agent},
        )
    return response.choices[0].message.content
