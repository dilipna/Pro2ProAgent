"""Rate-limit-aware retry for LLM calls.

Hosted LLM providers -- especially free/on-demand tiers (Groq's on-demand
gpt-oss tier caps at 8000 tokens/minute) -- return 429s as a matter of
course, not as an edge case. Treating that the same as a random transient
failure (blind exponential backoff) either retries too slowly or gives up
too early. Providers routinely tell you exactly how long to wait, in the
response body or a `retry-after` header; this module reads that and waits
the *right* amount, falling back to exponential backoff for everything
else.

This is the single retry seam used everywhere a real LLM call happens:
llm.py, the Research/Analyst agents, and the venture pipeline agents.
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

from langgraph.errors import GraphRecursionError

logger = logging.getLogger(__name__)

# Deterministic failures that carry no HTTP status code but will reproduce
# identically on every retry -- hitting an agent's tool-call step ceiling
# chief among them (see agents/research.py's MAX_RESEARCH_STEPS).
_NON_RETRYABLE_TYPES: tuple[type[Exception], ...] = (GraphRecursionError,)

# Provider error codes for a 400 that is actually a *stochastic* generation
# failure -- the model produced malformed tool-call JSON or output that
# didn't match the requested schema -- rather than a structurally invalid
# request. Observed live on Groq (`tool_use_failed`, `json_validate_failed`)
# with a smaller model occasionally garbling function-call syntax; a retry
# resamples and usually succeeds. This is the opposite lesson from the 413
# case above: same status code family, but here the *specific* code says
# "try again," not "this can never work."
_RETRYABLE_GENERATION_ERROR_CODES = ("tool_use_failed", "json_validate_failed")

_RETRY_AFTER_IN_MESSAGE = re.compile(r"try again in ([\d.]+)\s*s", re.IGNORECASE)

DEFAULT_ATTEMPTS = 4
DEFAULT_BASE_DELAY_S = 2.0
RATE_LIMIT_SAFETY_MARGIN_S = 0.5


def _extract_retry_after(exc: Exception) -> float | None:
    """Best-effort read of a provider-suggested wait time: the HTTP
    `retry-after` header when the client exposes a `.response` (OpenAI-
    compatible clients do), otherwise Groq/OpenRouter's convention of
    embedding it in the error message text (e.g. "...try again in 6.1s")."""
    response = getattr(exc, "response", None)
    if response is not None:
        header = getattr(response, "headers", {}).get("retry-after")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
    match = _RETRY_AFTER_IN_MESSAGE.search(str(exc))
    if match:
        return float(match.group(1))
    return None


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) if response is not None else None


def _is_rate_limit_error(exc: Exception) -> bool:
    """Whether `exc` represents a transient, worth-waiting-out rate limit.

    The HTTP status code is authoritative whenever it's known: 429 means
    "too many requests, try again"; any other 4xx is a different problem
    even if the provider's message text happens to say "rate_limit_exceeded"
    -- Groq's own 413 "payload permanently too large for this model's
    tokens-per-minute ceiling" reuses that exact wording, and retrying that
    is futile no matter how long you wait. Message-text matching is only a
    fallback for clients that don't expose a status code at all.
    """
    status = _status_code(exc)
    if status is not None:
        return status == 429
    text = str(exc).lower()
    return "rate limit" in text or "rate_limit" in text or "429" in text


def _is_stochastic_generation_error(exc: Exception) -> bool:
    """A 400 whose *specific* error code says the model's own output was
    malformed (bad tool-call JSON, schema mismatch), not that the request
    was invalid. Resampling on retry usually produces well-formed output."""
    text = str(exc)
    return any(code in text for code in _RETRYABLE_GENERATION_ERROR_CODES)


def _is_retryable(exc: Exception) -> bool:
    """429s and status-less (e.g. connection-level) failures are worth
    retrying, as are 400s that are actually stochastic generation failures
    (see `_is_stochastic_generation_error`). Any other 4xx -- bad request,
    auth, model not found, or a 413 payload-too-large -- will fail
    identically every time and should surface immediately rather than burn
    the retry budget. Same for framework-level deterministic failures like
    a recursion-limit trip."""
    if isinstance(exc, _NON_RETRYABLE_TYPES):
        return False
    if _is_stochastic_generation_error(exc):
        return True
    status = _status_code(exc)
    if status is not None:
        return status == 429
    return True


async def with_retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    agent: str,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY_S,
) -> T:
    """Runs `fn()`, retrying rate-limit and transient errors with
    provider-aware backoff. Non-retryable 4xx errors propagate immediately
    instead of wasting the retry budget on a request that will never
    succeed unmodified.
    """
    last_error: Exception | None = None
    tried = 0
    for attempt in range(1, attempts + 1):
        tried = attempt
        try:
            return await fn()
        except Exception as exc:
            last_error = exc
            if not _is_retryable(exc) or attempt == attempts:
                break
            if _is_rate_limit_error(exc):
                wait = (_extract_retry_after(exc) or base_delay * (2 ** (attempt - 1))) + RATE_LIMIT_SAFETY_MARGIN_S
                logger.warning(
                    "%s hit a rate limit (attempt %d/%d) -- waiting %.1fs", agent, attempt, attempts, wait
                )
            else:
                wait = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "%s call failed (attempt %d/%d): %s -- retrying in %.1fs",
                    agent, attempt, attempts, exc, wait,
                )
            await asyncio.sleep(wait)
    raise RuntimeError(f"{agent} failed after {tried} attempt(s)") from last_error
