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
from .resilience import with_retry

# Per-call retry, opt-in for multi-call agent loops only (`retry_calls_as`).
#
# A ReAct turn makes one model call per step with a growing history; retrying
# the *whole turn* on a 429 re-spends every earlier step's tokens. On an
# 8,000 TPM tier (Groq, 2026-09-15) that never converges -- observed live:
# research failed after 4 whole-turn attempts at "Used 7547, Requested 2174".
# Retrying only the call that hit the limit, after the provider's suggested
# wait, resumes the loop where it stopped. It is still the single retry seam
# (ADR-0005) and SDK retries stay off. Single-call sites (analyst, venture)
# already wrap their call in with_retry and must not opt in, or retries stack.


class RetryingChatOpenAI(ChatOpenAI):
    retry_agent: str = "llm"

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        parent = super()._agenerate
        return await with_retry(
            lambda: parent(messages, stop=stop, run_manager=run_manager, **kwargs), agent=self.retry_agent
        )


class RetryingChatAnthropic(ChatAnthropic):
    retry_agent: str = "llm"

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        parent = super()._agenerate
        return await with_retry(
            lambda: parent(messages, stop=stop, run_manager=run_manager, **kwargs), agent=self.retry_agent
        )


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
    retry_calls_as: str | None = None,
    reasoning_effort: Literal["low", "medium", "high"] | None = None,
):
    """`max_tokens` defaults conservatively -- low-credit accounts on
    OpenRouter (and similar) reject a request outright if a model's uncapped
    default output length costs more than the account can afford.
    `temperature=0` is used by the venture pipeline for reproducible,
    explainable outputs. `retry_calls_as` (agent label) turns on per-call
    retry for multi-call agent loops; see RetryingChatOpenAI above.

    `reasoning_effort` only takes effect on Groq (silently ignored on other
    providers, where it isn't a supported concept for the models configured
    here). A reasoning model like `gpt-oss-20b` spends hidden reasoning
    tokens before any visible output; found live via guardrails.py, a modest
    `max_tokens` tuned for a trivial classification can let that reasoning
    alone exhaust the budget and starve the model into an empty response
    (`finish_reason="length"`). "low" cuts that overhead sharply (measured:
    33 reasoning tokens instead of blowing a 300-token cap) for a task that
    never needed deep reasoning. Only ask for this on tasks that are
    genuinely trivial classification/extraction -- it trades away reasoning
    quality, which matters for scoring or idea generation.
    """
    settings = get_settings()
    provider, model_name = resolve_model(tier)
    extra: dict = {}
    if temperature is not None:
        extra["temperature"] = temperature
    openai_cls: type[ChatOpenAI] = ChatOpenAI
    anthropic_cls: type[ChatAnthropic] = ChatAnthropic
    if retry_calls_as:
        openai_cls, anthropic_cls = RetryingChatOpenAI, RetryingChatAnthropic
        extra["retry_agent"] = retry_calls_as
    if reasoning_effort is not None and provider == "groq":
        extra["extra_body"] = {"reasoning_effort": reasoning_effort}

    # A per-request network timeout so a wedged connection surfaces as a
    # retryable error (resilience.with_retry treats a status-less failure as
    # transient) instead of hanging a whole run. The SDK default is 10
    # minutes; that's far too long to sit blocked on a single call.
    timeout = settings.llm_request_timeout_s

    if provider == "openrouter":
        return openai_cls(
            model=model_name,
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            max_tokens=max_tokens,
            max_retries=0,
            timeout=timeout,
            **extra,
        )

    if provider == "groq":
        return openai_cls(
            model=model_name,
            api_key=settings.groq_api_key,
            base_url=GROQ_BASE_URL,
            max_tokens=max_tokens,
            max_retries=0,
            timeout=timeout,
            **extra,
        )

    return anthropic_cls(
        model=model_name,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        max_retries=0,
        timeout=timeout,
        **extra,
    )
