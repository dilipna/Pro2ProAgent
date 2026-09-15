"""Per-call retry for multi-call agent loops (chat_model.RetryingChatOpenAI).

Regression for a live failure on Groq's 8,000 TPM tier: retrying a whole
ReAct turn on a 429 re-spent every earlier step's tokens and never converged.
A 429 must retry only the call that hit it.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI

from p2pops import resilience
from p2pops.chat_model import RetryingChatOpenAI, get_chat_model
from p2pops.config import get_settings


class RateLimited(Exception):
    status_code = 429

    def __str__(self) -> str:
        return "Rate limit reached ... Please try again in 0.01s"


@pytest.fixture
def no_sleep(monkeypatch):
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(resilience.asyncio, "sleep", fake_sleep)
    return waits


async def test_a_429_retries_only_that_call(monkeypatch, no_sleep):
    calls = {"n": 0}

    async def flaky(self, messages, stop=None, run_manager=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimited()
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

    monkeypatch.setattr(ChatOpenAI, "_agenerate", flaky)
    model = RetryingChatOpenAI(model="m", api_key="k", max_retries=0, retry_agent="research.llm")
    result = await model.ainvoke([HumanMessage(content="hi")])

    assert result.content == "ok"
    assert calls["n"] == 2
    assert len(no_sleep) == 1 and no_sleep[0] == pytest.approx(0.01 + resilience.RATE_LIMIT_SAFETY_MARGIN_S)


def test_only_opted_in_callers_get_per_call_retry(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    get_settings.cache_clear()
    try:
        assert type(get_chat_model("default")) is ChatOpenAI
        retrying = get_chat_model("default", retry_calls_as="research.llm")
        assert isinstance(retrying, RetryingChatOpenAI) and retrying.retry_agent == "research.llm"
        assert retrying.max_retries == 0
    finally:
        get_settings.cache_clear()
