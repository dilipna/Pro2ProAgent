"""Builds a LangChain chat model for LangGraph agents, honoring whichever
provider is configured (Anthropic direct, or OpenRouter) so agent code
doesn't need to care which one is active.

Plain, non-agentic completions still go through llm.py's LiteLLM wrapper.
This module exists separately because LangGraph's create_react_agent needs
native tool-calling/binding, which LiteLLM's LangChain shim doesn't reliably
support yet -- so agents get a real langchain-anthropic / langchain-openai
chat model instead.
"""

from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from .config import OPENROUTER_BASE_URL, get_settings


def get_chat_model(
    tier: Literal["default", "builder"] = "default",
    max_tokens: int = 2048,
    temperature: float | None = None,
):
    """`max_tokens` defaults conservatively -- low-credit OpenRouter accounts
    reject a request outright if a model's uncapped default output length
    costs more than the account can afford. `temperature=0` is used by the
    venture pipeline for reproducible, explainable outputs.
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
            **extra,
        )

    model_name = settings.anthropic_builder_model if tier == "builder" else settings.anthropic_default_model
    return ChatAnthropic(
        model=model_name, api_key=settings.anthropic_api_key, max_tokens=max_tokens, **extra
    )
