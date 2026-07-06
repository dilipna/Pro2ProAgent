import pytest
from langgraph.errors import GraphRecursionError

from p2pops.resilience import _extract_retry_after, _is_retryable, with_retry


class RateLimitError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class BadRequestError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def test_extract_retry_after_parses_groq_style_message():
    exc = RateLimitError("Rate limit reached... Please try again in 6.105s.")
    assert _extract_retry_after(exc) == 6.105


def test_extract_retry_after_none_when_absent():
    assert _extract_retry_after(RateLimitError("something else broke")) is None


def test_is_retryable_rate_limit_and_non_4xx():
    assert _is_retryable(RateLimitError("rate limit", status_code=429))
    assert _is_retryable(RuntimeError("connection reset"))  # no status_code -> retryable


def test_is_retryable_false_for_other_4xx():
    assert not _is_retryable(BadRequestError("bad schema", status_code=400))


def test_413_payload_too_large_is_not_retryable_despite_rate_limit_wording():
    """Regression test: Groq's 413 "request too large for this model's
    tokens-per-minute ceiling" reuses the string "rate_limit_exceeded" in
    its error body. Status code must win over text -- retrying a
    structurally oversized request can never succeed, unlike a genuine 429
    which just needs a wait."""
    exc = BadRequestError(
        "Request too large for model `openai/gpt-oss-20b`... code: rate_limit_exceeded",
        status_code=413,
    )
    assert not _is_retryable(exc)


def test_graph_recursion_error_is_not_retryable():
    """A step-ceiling trip (e.g. MAX_RESEARCH_STEPS) is deterministic --
    the same conversation will hit the same ceiling every time, so
    retrying just burns budget for a guaranteed-identical failure."""
    assert not _is_retryable(GraphRecursionError("Recursion limit reached"))


def test_stochastic_generation_400_is_retryable_despite_status_code():
    """Regression test: a live run on Groq's llama-4-scout produced
    malformed tool-call JSON (`tool_use_failed`) and, separately, a
    schema-violating structured output (`json_validate_failed`). Both are
    400s, but they're the model's *sampling* going wrong, not a broken
    request -- unlike the 413 case, resampling on retry routinely fixes it,
    so these specific codes must override the generic "400 = give up" rule."""
    tool_use = BadRequestError(
        "Failed to call a function. code: tool_use_failed", status_code=400
    )
    schema_mismatch = BadRequestError(
        "does not validate with schema. code: json_validate_failed", status_code=400
    )
    assert _is_retryable(tool_use)
    assert _is_retryable(schema_mismatch)


async def test_with_retry_succeeds_after_transient_failures(monkeypatch):
    sleeps = []
    monkeypatch.setattr("p2pops.resilience.asyncio.sleep", lambda s: sleeps.append(s) or _noop())

    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    result = await with_retry(flaky, agent="test", attempts=4, base_delay=1.0)
    assert result == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2  # two failures before success


async def test_with_retry_honors_provider_wait_time(monkeypatch):
    waits = []
    monkeypatch.setattr("p2pops.resilience.asyncio.sleep", lambda s: waits.append(s) or _noop())

    calls = {"n": 0}

    async def rate_limited_then_ok():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimitError("Rate limit... try again in 3.2s.", status_code=429)
        return "ok"

    result = await with_retry(rate_limited_then_ok, agent="test")
    assert result == "ok"
    assert waits[0] == pytest.approx(3.7)  # provider hint + 0.5s safety margin


async def test_with_retry_does_not_retry_non_retryable_errors(monkeypatch):
    calls = {"n": 0}

    async def always_bad_request():
        calls["n"] += 1
        raise BadRequestError("invalid schema")

    # Message must report the true attempt count (1), not the configured
    # max (5) -- regression test for a bug where a non-retryable error that
    # bailed out early was misreported as having exhausted every attempt.
    with pytest.raises(RuntimeError, match=r"failed after 1 attempt"):
        await with_retry(always_bad_request, agent="test", attempts=5)
    assert calls["n"] == 1  # gave up immediately, did not burn the retry budget


async def test_with_retry_raises_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr("p2pops.resilience.asyncio.sleep", lambda s: _noop())

    calls = {"n": 0}

    async def always_transient():
        calls["n"] += 1
        raise RuntimeError("still broken")

    with pytest.raises(RuntimeError, match="failed after 3 attempt"):
        await with_retry(always_transient, agent="test", attempts=3)
    assert calls["n"] == 3


async def _noop():
    return None
