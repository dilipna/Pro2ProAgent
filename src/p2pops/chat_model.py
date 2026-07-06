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
    extra: dict = {}
    if temperature is not None:
        extra["temperature"] = temperature

    if settings.llm_provider == "openrouter":
        model_name = (
            settings.openrouter_builder_model if tier == "builder" else settings.openrouter_default_model
        )
        return ChatOpenAI(
            model=model_name,
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            max_tokens=max_tokens,
            max_retries=0,
            **extra,
        )

    if settings.llm_provider == "groq":
        model_name = settings.groq_builder_model if tier == "builder" else settings.groq_default_model
        return ChatOpenAI(
            model=model_name,
            api_key=settings.groq_api_key,
            base_url=GROQ_BASE_URL,
            max_tokens=max_tokens,
            max_retries=0,
            **extra,
        )

    model_name = settings.anthropic_builder_model if tier == "builder" else settings.anthropic_default_model
    return ChatAnthropic(
        model=model_name,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        max_retries=0,
        **extra,
    )
