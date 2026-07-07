"""Builds a LangChain chat model for LangGraph agents, honoring whichever
provider is configured (Anthropic direct, OpenRouter, or Groq) so agent
code doesn't need to care which one is active.

Plain, non-agentic completions still go through llm.py's LiteLLM wrapper.
This module exists separately because LangGraph's create_react_agent needs
native tool-calling/binding, which LiteLLM's LangChain shim doesn't reliably
support yet -- so agents get a real langchain-anthropic / langchain-openai
chat model instead. OpenRouter and Groq both expose OpenAI-compatible
endpoints, so ChatOpenAI + base_url covers them without extra dependencies.

`max_retries=0` is deliberate: our own `resilience.with_retry` is the single
place retry policy is decided (rate-limit-aware backoff, non-retryable 4xx
bails immediately). Leaving the SDK's own default retries on stacks a second,
uncoordinated retry layer underneath ours -- observed live, this cost
several extra minutes of invisible 429 backoff before our code ever saw the
error and could reason about it.
"""

from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from .config import GROQ_BASE_URL, OPENROUTER_BASE_URL, get_settings


def resolve_model(tier: Literal["default", "builder"] = "default") -> tuple[str, str]:
    """(provider, bare_model_name) for the active provider/tier -- the exact
    model id `get_chat_model` passes to the SDK. Exposed separately so
    `cost_tracking.py` can attribute usage to the same model id actually
    called, without duplicating (and risking drift from) this branching."""
    settings = get_settings()
    if settings.llm_provider == "openrouter":
        model = settings.openrouter_builder_model if tier == "builder" else settings.openrouter_default_model
    elif settings.llm_provider == "groq":
        model = settings.groq_builder_model if tier == "builder" else settings.groq_default_model
    else:
        model = settings.anthropic_builder_model if tier == "builder" else settings.anthropic_default_model
    return settings.llm_provider, model


def get_chat_model(
    tier: Literal["default", "builder"] = "default",
    max_tokens: int = 2048,
    temperature: float | None = None,
):
    """`max_tokens` defaults conservatively -- low-credit accounts on
    OpenRouter (and similar) reject a request outright if a model's uncapped
    default output length costs more than the account can afford.
    `temperature=0` is used by the venture pipeline for reproducible,
    explainable outputs.
    """
    settings = get_settings()
    provider, model_name = resolve_model(tier)
    extra: dict = {}
    if temperature is not None:
        extra["temperature"] = temperature

    if provider == "openrouter":
        return ChatOpenAI(
            model=model_name,
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            max_tokens=max_tokens,
            max_retries=0,
            **extra,
        )

    if provider == "groq":
        return ChatOpenAI(
            model=model_name,
            api_key=settings.groq_api_key,
            base_url=GROQ_BASE_URL,
            max_tokens=max_tokens,
            max_retries=0,
            **extra,
        )

    return ChatAnthropic(
        model=model_name,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        max_retries=0,
        **extra,
    )
