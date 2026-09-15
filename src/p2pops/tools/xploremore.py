"""XploreMore problem discovery: API client, circuit breaker, agent tools
and provenance (ADR-0012).

XploreMore (a separate system) ingests discussions from Hacker News, GitHub
issues, Lobsters and Stack Exchange, classifies pain points, clusters
duplicates into problems and ranks them by demand. The Research Agent asks it
first, then validates or fills gaps with its own HN/web tools.

Contract: `contracts/xploremore/problems.v1.openapi.json` (vendored copy;
tests validate every mocked payload and every request's query parameters
against it).

Failure policy -- discovery must never depend on XploreMore being up:
- 5 s timeout per request; a timeout, connection error, 5xx, 401/403 or an
  unparseable payload counts as a failure.
- Circuit breaker: 3 consecutive failures open it for 60 s. While open the
  research agent is not offered these tools at all (agents/research.py
  decides that in code, not the LLM).
- 429 holds the breaker open for `Retry-After` seconds without counting as a
  failure: the service is healthy, we are simply over quota.
- A tool call that fails mid-run returns an explicit non-empty "unavailable"
  result telling the agent to use search_hacker_news/search_web (an empty
  tool result breaks Groq, see mcp/server.py).

Token budget: the agent resends every tool result on each turn and Groq's
tier here is 8,000 TPM, so results are compact (short statement, two
truncated evidence excerpts per problem), mirroring XploreMore's own MCP
server.
"""

from __future__ import annotations

import ast
import json
import logging
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx

from p2pops.config import get_settings
from p2pops.models import ResearchReport, XploreMoreProvenance

logger = logging.getLogger(__name__)

TOOL_NAMES = frozenset({"find_problems", "get_problem"})
Category = Literal["bug_or_reliability", "cost_or_performance", "missing_capability", "workflow_friction"]

EXCERPT_CHARS = 200
STATEMENT_CHARS = 240
MAX_PROBLEMS = 10  # contract allows 25; more than 10 never fits the token budget
LIST_EVIDENCE = 2  # contract allows 5 per problem on the list endpoint
MAX_DETAIL_EVIDENCE = 5  # contract allows 25
MAX_PROVENANCE_URLS = 5
MAX_RETRY_AFTER_S = 3600.0
FALLBACK_HINT = "Use search_hacker_news and search_web instead."


class XploreMoreError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class XploreMoreUnavailable(XploreMoreError):
    def __init__(self, reason: str, retry_after_s: float | None = None) -> None:
        super().__init__(reason)
        self.retry_after_s = retry_after_s


class ProblemNotFound(XploreMoreError):
    pass


class CircuitBreaker:
    """Consecutive-failure breaker with a Retry-After hold.

    closed -> open after `failure_threshold` consecutive failures, for
    `open_s` seconds -> half-open: calls are allowed again; one success
    closes it, one more failure re-opens it immediately. `hold(seconds)`
    blocks calls for a server-requested period without touching the failure
    count. Not a strict single-trial half-open: concurrent research runs may
    each send one trial request, which is acceptable at this call volume.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        open_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.open_s = open_s
        self._clock = clock
        self.failures = 0
        self._blocked_until: float | None = None

    @property
    def state(self) -> str:
        if self._blocked_until is not None and self._clock() < self._blocked_until:
            return "open"
        return "half_open" if self.failures >= self.failure_threshold else "closed"

    def allow(self) -> bool:
        return self.state != "open"

    def retry_in(self) -> float:
        if self._blocked_until is None:
            return 0.0
        return max(0.0, self._blocked_until - self._clock())

    def record_success(self) -> None:
        self.failures = 0
        self._blocked_until = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self._block_for(self.open_s)

    def hold(self, seconds: float) -> None:
        self._block_for(seconds)

    def _block_for(self, seconds: float) -> None:
        until = self._clock() + seconds
        self._blocked_until = until if self._blocked_until is None else max(self._blocked_until, until)


def parse_retry_after(value: str | None, default: float) -> float:
    """Retry-After is either delta-seconds or an HTTP-date (RFC 9110)."""
    if not value:
        return default
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return default
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = (when - datetime.now(UTC)).total_seconds()
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_S)


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _compact(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": p["id"],
        "statement": _short(p["statement"], STATEMENT_CHARS),
        "category": p["category"],
        "demand": round(p["demand_score"], 2),
        "voices": p["voice_count"],
        "sources": p["source_count"],
        "platforms": p["platforms"],
        "last_seen": p["last_seen"][:10],
        "evidence": [
            {"url": e["url"], "platform": e["platform"], "excerpt": _short(e["excerpt"], EXCERPT_CHARS)}
            for e in p["evidence"]
        ],
    }
    if p.get("relevance") is not None:
        out["relevance"] = round(p["relevance"], 2)
    return out


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(int(value), high))


class XploreMoreClient:
    """Async client for XploreMore's `/v1/problems` API.

    A fresh `httpx.AsyncClient` per request: the pipeline runs on the API's
    event loop, the CLI on its own `asyncio.run` loop, and tests on one loop
    per test -- a pooled client bound to a dead loop fails in confusing ways,
    while the extra TCP handshake is negligible next to an LLM turn. The
    breaker, which is what must persist, is passed in.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout_s: float = 5.0,
        breaker: CircuitBreaker | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.breaker = breaker or CircuitBreaker()
        self._transport = transport
        self._headers = {"User-Agent": "p2pops-research/0.1", "Accept": "application/json"}
        if api_key:
            self._headers["X-XM-Api-Key"] = api_key

    async def _get[T](self, path: str, params: dict[str, Any], shape: Callable[[Any], T]) -> T:
        if not self.breaker.allow():
            raise XploreMoreUnavailable("circuit_open", self.breaker.retry_in())
        clean = {k: v for k, v in params.items() if v is not None}
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=httpx.Timeout(self.timeout_s),
                transport=self._transport,
            ) as http:
                response = await http.get(path, params=clean)
        except httpx.HTTPError as exc:
            self.breaker.record_failure()
            raise XploreMoreUnavailable(f"unreachable:{type(exc).__name__}") from exc

        status = response.status_code
        if status == 429:
            wait = parse_retry_after(response.headers.get("Retry-After"), self.breaker.open_s)
            self.breaker.hold(wait)
            raise XploreMoreUnavailable("rate_limited", wait)
        if status == 404:
            self.breaker.record_success()  # the service answered; the id doesn't exist
            raise ProblemNotFound("not_found")
        if status >= 500 or status in (401, 403):
            # 401/403 is a configuration fault that no retry fixes: opening the
            # breaker stops every run from paying for it again for a while.
            self.breaker.record_failure()
            raise XploreMoreUnavailable(f"http_{status}")
        if status >= 400:
            # 422 etc.: the service is healthy and our request was wrong.
            self.breaker.record_success()
            raise XploreMoreError(f"http_{status}")
        try:
            shaped = shape(response.json())
        except (ValueError, KeyError, TypeError) as exc:
            self.breaker.record_failure()
            raise XploreMoreUnavailable("bad_payload") from exc
        self.breaker.record_success()
        return shaped

    async def find_problems(
        self,
        topic: str | None = None,
        category: str | None = None,
        since_days: int = 30,
        min_voices: int = 2,
        limit: int = 5,
    ) -> dict[str, Any]:
        topic = " ".join((topic or "").split())[:256] or None
        if topic is not None and len(topic) < 2:
            topic = None
        params = {
            "topic": topic,
            "category": category,
            "since_days": _clamp(since_days, 1, 90),
            "min_voices": _clamp(min_voices, 1, 100),
            "limit": _clamp(limit, 1, MAX_PROBLEMS),
            "evidence": LIST_EVIDENCE,
        }

        def shape(data: dict[str, Any]) -> dict[str, Any]:
            return {"ranker": data["ranker"], "problems": [_compact(p) for p in data["results"]]}

        result = await self._get("/v1/problems", params, shape)
        if not result["problems"] and params["min_voices"] > 1:
            # A narrow topic often has real single-voice problems only; say so
            # explicitly instead of returning nothing.
            result = await self._get("/v1/problems", {**params, "min_voices": 1}, shape)
            result["note"] = "No multi-voice problems matched; these have a single voice each."
        return result

    async def get_problem(self, problem_id: int, evidence: int = 3) -> dict[str, Any]:
        params = {"evidence": _clamp(evidence, 1, MAX_DETAIL_EVIDENCE)}

        def shape(data: dict[str, Any]) -> dict[str, Any]:
            return {
                **_compact(data),
                "members": data["member_count"],
                "first_seen": data["first_seen"][:10],
                "demand_factors": {k: round(v, 3) for k, v in data["demand_factors"].items()},
            }

        return await self._get(f"/v1/problems/{int(problem_id)}", params, shape)


# --- process-level wiring ----------------------------------------------------

_breaker: CircuitBreaker | None = None
# Tests inject an httpx.MockTransport here; production leaves it None.
_transport: httpx.AsyncBaseTransport | None = None


def breaker() -> CircuitBreaker:
    global _breaker
    if _breaker is None:
        settings = get_settings()
        _breaker = CircuitBreaker(settings.xploremore_breaker_failures, settings.xploremore_breaker_open_s)
    return _breaker


def reset() -> None:
    """Forget breaker state (tests, and config changes at runtime)."""
    global _breaker
    _breaker = None


def get_client() -> XploreMoreClient | None:
    settings = get_settings()
    if not settings.xploremore_api_url:
        return None
    return XploreMoreClient(
        settings.xploremore_api_url,
        settings.xploremore_api_key,
        timeout_s=settings.xploremore_timeout_s,
        breaker=breaker(),
        transport=_transport,
    )


def availability() -> str:
    """"ok", "not_configured" or "circuit_open" -- decided before the agent
    is built, so an unusable XploreMore is never even offered as a tool."""
    if not get_settings().xploremore_api_url:
        return "not_configured"
    return "ok" if breaker().allow() else "circuit_open"


# --- agent tools (shared by the in-process and MCP transports) ---------------


def _unavailable(reason: str) -> dict[str, Any]:
    return {"unavailable": reason, "fallback": FALLBACK_HINT}


async def find_problems(
    topic: str,
    category: Category | None = None,
    since_days: int = 30,
    min_voices: int = 2,
    limit: int = 5,
) -> dict[str, Any]:
    """Find real problems people report (HN, GitHub issues, Lobsters, Stack Exchange), already clustered and ranked by demand. Each has an id, voices (distinct people), sources and evidence URLs."""
    client = get_client()
    if client is None:
        return _unavailable("not_configured")
    try:
        result = await client.find_problems(topic, category, since_days, min_voices, limit)
    except XploreMoreError as exc:
        logger.warning("XploreMore find_problems failed: %s", exc.reason)
        return _unavailable(exc.reason)
    if not result["problems"]:
        return {"info": f"XploreMore has no problems matching '{topic}'.", "fallback": FALLBACK_HINT}
    return result


async def get_problem(problem_id: int, evidence: int = 3) -> dict[str, Any]:
    """Get one XploreMore problem by id with more evidence posts and its demand breakdown."""
    client = get_client()
    if client is None:
        return _unavailable("not_configured")
    try:
        return await client.get_problem(problem_id, evidence)
    except ProblemNotFound:
        return {"info": f"XploreMore has no problem {problem_id}."}
    except XploreMoreError as exc:
        logger.warning("XploreMore get_problem failed: %s", exc.reason)
        return _unavailable(exc.reason)


# --- provenance ----------------------------------------------------------------


def _parse_tool_content(content: Any) -> Any:
    """ToolMessage content is a JSON string (in-process tools), a list of
    text blocks (MCP adapter), or occasionally a Python repr."""
    if isinstance(content, list):
        texts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in content]
        content = "".join(texts)
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except ValueError:
        try:
            return ast.literal_eval(content)
        except (ValueError, SyntaxError):
            return None


def observe_tool_messages(messages: Iterable[Any]) -> tuple[dict[int, dict[str, Any]], list[str]]:
    """Problems the agent actually received (id -> compact problem), plus
    the reasons of any "unavailable" results. Reading the conversation
    rather than a side channel works identically for both transports."""
    ledger: dict[int, dict[str, Any]] = {}
    unavailable: list[str] = []
    for message in messages:
        if getattr(message, "type", None) != "tool" or getattr(message, "name", None) not in TOOL_NAMES:
            continue
        payload = _parse_tool_content(message.content)
        if not isinstance(payload, dict):
            continue
        if "unavailable" in payload:
            unavailable.append(str(payload["unavailable"]))
        problems = payload.get("problems") if "problems" in payload else [payload]
        for p in problems or []:
            if not isinstance(p, dict) or not isinstance(p.get("id"), int) or "voices" not in p:
                continue
            known = ledger.get(p["id"])
            if known is None:
                ledger[p["id"]] = p
            else:
                urls = {e["url"] for e in known.get("evidence", [])}
                extra = [e for e in p.get("evidence", []) if e.get("url") not in urls]
                known["evidence"] = known.get("evidence", []) + extra
    return ledger, unavailable


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/")


def provenance_for(problem: dict[str, Any]) -> XploreMoreProvenance:
    return XploreMoreProvenance(
        problem_id=problem["id"],
        voices=problem["voices"],
        sources=problem["sources"],
        platforms=list(problem.get("platforms", [])),
        demand=problem.get("demand"),
        evidence_urls=[e["url"] for e in problem.get("evidence", [])][:MAX_PROVENANCE_URLS],
    )


def attach_provenance(report: ResearchReport, ledger: dict[int, dict[str, Any]]) -> ResearchReport:
    """Code decides provenance; the model only proposes a problem_id.

    - The proposed id is kept only if the agent really received that problem.
    - Otherwise, an idea whose source_url is an evidence URL of exactly one
      received problem is linked to it.
    - Anything else gets no provenance (and a hallucinated id is dropped).
    """
    by_url: dict[str, set[int]] = {}
    for pid, problem in ledger.items():
        for e in problem.get("evidence", []):
            by_url.setdefault(_norm_url(e["url"]), set()).add(pid)

    ideas = []
    for idea in report.ideas:
        pid = idea.problem_id if idea.problem_id in ledger else None
        if pid is None:
            matches = by_url.get(_norm_url(idea.source_url), set())
            if len(matches) == 1:
                pid = next(iter(matches))
        if idea.problem_id is not None and pid != idea.problem_id:
            logger.info("dropping unverified XploreMore problem_id %s on %r", idea.problem_id, idea.title)
        provenance = provenance_for(ledger[pid]) if pid is not None else None
        ideas.append(idea.model_copy(update={"problem_id": pid, "provenance": provenance}))
    return report.model_copy(update={"ideas": ideas})
