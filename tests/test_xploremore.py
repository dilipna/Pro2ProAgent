"""XploreMore integration (ADR-0012): client, circuit breaker, 429 handling,
code-level fallback, provenance, and the consumer side of the contract test.

No network: XploreMore is mocked with httpx.MockTransport, and every mocked
payload and every outgoing query string is validated against the vendored
OpenAPI contract (contracts/xploremore/problems.v1.openapi.json).
"""

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import jsonschema
import pytest
from langchain_core.messages import AIMessage, ToolMessage

from conftest import make_idea
from p2pops.agents import analyst, research
from p2pops.api.schemas import IdeaOut
from p2pops.config import get_settings
from p2pops.db import repository as repo
from p2pops.models import DiscoveredIdea, ResearchReport, XploreMoreProvenance
from p2pops.tools import xploremore
from p2pops.tools.xploremore import (
    CircuitBreaker,
    XploreMoreClient,
    XploreMoreError,
    XploreMoreUnavailable,
    parse_retry_after,
)

CONTRACT = json.loads(
    (Path(__file__).parents[1] / "contracts" / "xploremore" / "problems.v1.openapi.json").read_text(
        encoding="utf-8"
    )
)
BASE = "http://xm.test"


# --- contract helpers ------------------------------------------------------------


def validate(schema_name: str, payload: dict) -> None:
    schema = {"$ref": f"#/components/schemas/{schema_name}", "components": CONTRACT["components"]}
    jsonschema.Draft202012Validator(schema).validate(payload)


def assert_query_matches_contract(request: httpx.Request, path_template: str) -> None:
    declared = {
        p["name"]: p["schema"] for p in CONTRACT["paths"][path_template]["get"]["parameters"] if p["in"] == "query"
    }
    for name, raw in request.url.params.multi_items():
        assert name in declared, f"query parameter {name!r} is not in the contract"
        schema = declared[name]
        types = {schema.get("type")} | {s.get("type") for s in schema.get("anyOf", [])}
        value = int(raw) if "integer" in types else raw
        jsonschema.Draft202012Validator(schema).validate(value)


def evidence(n: int, platform: str = "github") -> dict:
    return {
        "source_id": f"src-{n}",
        "platform": platform,
        "url": f"https://github.com/acme/agents/issues/{n}",
        "excerpt": ("Tool calls silently drop arguments when the schema has nested objects. " * 3)[:280],
        "engagement": {"points": None, "comments": 4, "reactions": 12},
        "date": "2026-09-10T12:00:00Z",
        "p_problem": 0.91,
    }


def summary(pid: int, voices: int = 5, sources: int = 3, relevance: float | None = 0.8) -> dict:
    return {
        "id": pid,
        "statement": "Agent frameworks drop tool-call arguments for nested JSON schemas, " * 6,
        "category": "bug_or_reliability",
        "demand_score": 3.14159,
        "voice_count": voices,
        "source_count": sources,
        "platforms": ["github", "hn"],
        "first_seen": "2026-08-20T00:00:00Z",
        "last_seen": "2026-09-12T08:30:00Z",
        "entities": ["langgraph"],
        "relevance": relevance,
        "evidence": [evidence(pid * 10 + 1), evidence(pid * 10 + 2, "hn")],
    }


def detail(pid: int) -> dict:
    return {
        **summary(pid, relevance=None),
        "effective_voices": 4.5,
        "member_count": 7,
        "demand_factors": {"voices": 1.8, "sources": 1.69, "recency": 0.93, "engagement": 1.4, "category": 1.0},
        "scorer_version": "demand-v0",
    }


def problems_response(results: list[dict]) -> dict:
    return {"as_of": "2026-09-15T10:00:00Z", "ranker": "rrf+demand-v0", "degraded": [], "results": results}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def client_with(handler, clock: FakeClock | None = None) -> XploreMoreClient:
    breaker = CircuitBreaker(3, 60.0, clock=clock or FakeClock())
    return XploreMoreClient(BASE, "xm_test_key", breaker=breaker, transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    # Environment beats .env, so a developer's local XPLOREMORE_* never leaks in.
    monkeypatch.setenv("XPLOREMORE_API_URL", "")
    monkeypatch.setenv("XPLOREMORE_API_KEY", "")
    get_settings.cache_clear()
    xploremore.reset()
    monkeypatch.setattr(xploremore, "_transport", None)
    yield
    xploremore.reset()
    get_settings.cache_clear()


@pytest.fixture
def configured(monkeypatch):
    """XploreMore configured at BASE; returns a function installing a handler."""
    monkeypatch.setenv("XPLOREMORE_API_URL", BASE)
    monkeypatch.setenv("XPLOREMORE_API_KEY", "xm_test_key")
    get_settings.cache_clear()
    xploremore.reset()

    def install(handler) -> None:
        monkeypatch.setattr(xploremore, "_transport", httpx.MockTransport(handler))

    return install


# --- contract ---------------------------------------------------------------------


def test_fixtures_satisfy_the_vendored_contract_and_the_validator_is_real():
    validate("ProblemsResponse", problems_response([summary(1), summary(2)]))
    validate("ProblemDetail", detail(1))
    broken = summary(1)
    del broken["voice_count"]
    with pytest.raises(jsonschema.ValidationError):
        validate("ProblemSummary", broken)


async def test_find_problems_sends_key_timeout_and_contract_params_then_compacts():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.path == "/v1/problems"
        assert_query_matches_contract(request, "/v1/problems")
        payload = problems_response([summary(1), summary(2), summary(3)])
        validate("ProblemsResponse", payload)
        return httpx.Response(200, json=payload)

    client = client_with(handler)
    # Out-of-range inputs from an LLM are clamped into the contract's bounds.
    result = await client.find_problems("tool calling bugs", since_days=500, min_voices=0, limit=99)

    request = seen[0]
    assert request.headers["X-XM-Api-Key"] == "xm_test_key"
    assert request.extensions["timeout"] == {"connect": 5.0, "read": 5.0, "write": 5.0, "pool": 5.0}
    assert request.url.params["limit"] == "10" and request.url.params["since_days"] == "90"

    assert result["ranker"] == "rrf+demand-v0"
    first = result["problems"][0]
    assert set(first) == {
        "id", "statement", "category", "demand", "voices", "sources", "platforms", "last_seen", "evidence",
        "relevance",
    }
    assert first["demand"] == 3.14 and first["last_seen"] == "2026-09-12"
    assert len(first["statement"]) <= xploremore.STATEMENT_CHARS
    assert all(set(e) == {"url", "platform", "excerpt"} for e in first["evidence"])
    assert all(len(e["excerpt"]) <= xploremore.EXCERPT_CHARS for e in first["evidence"])
    # Compact by design. Worst case here -- every statement and excerpt at its
    # cap -- is ~3.1k characters (~800 tokens) for three problems.
    assert len(json.dumps(result)) < 3500


async def test_empty_multi_voice_result_is_relaxed_to_single_voice_and_says_so():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert_query_matches_contract(request, "/v1/problems")
        calls.append(request.url.params["min_voices"])
        results = [] if request.url.params["min_voices"] == "2" else [summary(4, voices=1, sources=1)]
        return httpx.Response(200, json=problems_response(results))

    result = await client_with(handler).find_problems("niche topic")
    assert calls == ["2", "1"]
    assert result["problems"][0]["voices"] == 1
    assert "single voice" in result["note"]


async def test_get_problem_detail_is_compact_and_404_is_not_an_outage():
    def handler(request: httpx.Request) -> httpx.Response:
        assert_query_matches_contract(request, "/v1/problems/{problem_id}")
        if request.url.path == "/v1/problems/7":
            payload = detail(7)
            validate("ProblemDetail", payload)
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"detail": "not found"})

    client = client_with(handler)
    result = await client.get_problem(7, evidence=50)
    assert result["members"] == 7 and result["first_seen"] == "2026-08-20"
    assert result["demand_factors"]["sources"] == 1.69

    with pytest.raises(xploremore.ProblemNotFound):
        await client.get_problem(8)
    assert client.breaker.failures == 0


# --- circuit breaker ----------------------------------------------------------------


async def test_breaker_opens_after_three_failures_and_closes_after_a_trial_success():
    clock = FakeClock()
    hits = {"n": 0, "healthy": False}

    def handler(request: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        if hits["healthy"]:
            return httpx.Response(200, json=problems_response([summary(1)]))
        return httpx.Response(503)

    client = client_with(handler, clock)
    for _ in range(3):
        with pytest.raises(XploreMoreUnavailable, match="http_503"):
            await client.find_problems("x")
    assert client.breaker.state == "open"

    # Open: no request reaches the service.
    with pytest.raises(XploreMoreUnavailable, match="circuit_open") as info:
        await client.find_problems("x")
    assert hits["n"] == 3
    assert info.value.retry_after_s == 60.0

    clock.now += 59.9
    assert client.breaker.state == "open"
    clock.now += 0.1
    assert client.breaker.state == "half_open"

    hits["healthy"] = True
    result = await client.find_problems("x")
    assert result["problems"][0]["id"] == 1
    assert client.breaker.state == "closed" and client.breaker.failures == 0


async def test_a_failed_trial_in_half_open_reopens_immediately():
    clock = FakeClock()
    client = client_with(lambda request: httpx.Response(500), clock)
    for _ in range(3):
        with pytest.raises(XploreMoreUnavailable):
            await client.find_problems("x")
    clock.now += 60
    with pytest.raises(XploreMoreUnavailable, match="http_500"):
        await client.find_problems("x")
    assert client.breaker.state == "open"


@pytest.mark.parametrize(
    "exc", [httpx.ReadTimeout("read timed out"), httpx.ConnectError("connection refused")]
)
async def test_timeouts_and_connection_errors_count_as_failures(exc):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    client = client_with(handler)
    for _ in range(3):
        with pytest.raises(XploreMoreUnavailable, match=f"unreachable:{type(exc).__name__}"):
            await client.find_problems("x")
    assert client.breaker.state == "open"


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(200, json={"unexpected": True}), "bad_payload"),
        (httpx.Response(200, text="<html>proxy error</html>"), "bad_payload"),
        (httpx.Response(401, json={"detail": "invalid key"}), "http_401"),
    ],
)
async def test_bad_payloads_and_rejected_keys_count_as_failures(response, reason):
    client = client_with(lambda request: response)
    with pytest.raises(XploreMoreUnavailable, match=reason):
        await client.find_problems("x")
    assert client.breaker.failures == 1


async def test_client_errors_do_not_trip_the_breaker():
    client = client_with(lambda request: httpx.Response(422, json={"detail": []}))
    with pytest.raises(XploreMoreError, match="http_422"):
        await client.find_problems("x")
    assert client.breaker.failures == 0 and client.breaker.state == "closed"


# --- 429 ----------------------------------------------------------------------------


async def test_429_honours_retry_after_even_beyond_the_breaker_window():
    clock = FakeClock()
    hits = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        if hits["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "120"})
        return httpx.Response(200, json=problems_response([summary(1)]))

    client = client_with(handler, clock)
    with pytest.raises(XploreMoreUnavailable, match="rate_limited") as info:
        await client.find_problems("x")
    assert info.value.retry_after_s == 120.0
    # Rate limiting is not an outage: the failure count is untouched...
    assert client.breaker.failures == 0
    # ...but no request is sent until Retry-After has passed, even after the
    # breaker's own 60 s window.
    clock.now += 60
    with pytest.raises(XploreMoreUnavailable, match="circuit_open"):
        await client.find_problems("x")
    assert hits["n"] == 1
    clock.now += 60
    assert (await client.find_problems("x"))["problems"]
    assert hits["n"] == 2


def test_retry_after_parsing():
    assert parse_retry_after("11", 60) == 11
    assert parse_retry_after(None, 60) == 60
    assert parse_retry_after("soon", 60) == 60
    assert parse_retry_after("-5", 60) == 0
    assert parse_retry_after("999999", 60) == xploremore.MAX_RETRY_AFTER_S
    http_date = format_datetime(datetime.now(UTC) + timedelta(seconds=90), usegmt=True)
    assert 85 <= parse_retry_after(http_date, 60) <= 90


# --- fallback decided in code --------------------------------------------------------

BASE_TOOLS = {"search_hacker_news", "search_web", "read_article"}


async def test_unconfigured_xploremore_is_never_offered(monkeypatch):
    monkeypatch.setenv("RESEARCH_TOOLS", "in_process")
    get_settings.cache_clear()
    assert xploremore.availability() == "not_configured"
    tools, transport = await research._research_tools()
    assert {t.name for t in tools} == BASE_TOOLS
    # And a direct call (e.g. an external MCP client) gets an explicit, non-empty answer.
    result = await xploremore.find_problems("anything")
    assert result["unavailable"] == "not_configured" and result["fallback"]


async def test_open_breaker_withdraws_the_tools_until_it_recovers(monkeypatch, configured):
    monkeypatch.setenv("RESEARCH_TOOLS", "in_process")
    get_settings.cache_clear()
    clock = FakeClock()
    monkeypatch.setattr(xploremore, "_breaker", CircuitBreaker(3, 60.0, clock=clock))
    configured(lambda request: httpx.Response(503))

    tools, _ = await research._research_tools()
    assert {t.name for t in tools} == BASE_TOOLS | xploremore.TOOL_NAMES

    # Mid-run failures come back to the agent as explicit fallback instructions.
    for _ in range(3):
        result = await xploremore.find_problems("agent memory")
        assert result["unavailable"] == "http_503" and "search_hacker_news" in result["fallback"]

    assert xploremore.availability() == "circuit_open"
    tools, _ = await research._research_tools()
    assert {t.name for t in tools} == BASE_TOOLS

    clock.now += 60
    tools, _ = await research._research_tools()
    assert {t.name for t in tools} == BASE_TOOLS | xploremore.TOOL_NAMES


async def test_mcp_transport_drops_xploremore_tools_when_unavailable(monkeypatch):
    monkeypatch.setenv("RESEARCH_TOOLS", "mcp")
    get_settings.cache_clear()
    monkeypatch.setattr(research, "_mcp_unhealthy", False)
    names = BASE_TOOLS | xploremore.TOOL_NAMES

    class Named:
        def __init__(self, name):
            self.name = name

    async def fake_mcp_tools():
        return [Named(n) for n in names]

    monkeypatch.setattr(research, "_mcp_tools", fake_mcp_tools)
    tools, transport = await research._research_tools()
    assert transport == "mcp"
    assert {t.name for t in tools} == BASE_TOOLS


def test_prompt_and_step_budget_follow_the_bound_tools(monkeypatch):
    captured = {}

    def fake_agent(model, tools, prompt, response_format):
        captured["prompt"] = prompt
        return object()

    monkeypatch.setattr(research, "create_react_agent", fake_agent)
    monkeypatch.setattr(research, "get_chat_model", lambda role, **kwargs: None)

    research._build_agent(research._in_process_tools(False))
    assert captured["prompt"] == research.RESEARCH_SYSTEM_PROMPT

    research._build_agent(research._in_process_tools(True))
    assert captured["prompt"] == research.XPLOREMORE_RESEARCH_PROMPT
    assert "find_problems" in captured["prompt"] and "Never invent a problem_id" in captured["prompt"]


# --- provenance ----------------------------------------------------------------------


def _tool_messages() -> list:
    listed = {"ranker": "r", "problems": [xploremore._compact(summary(1)), xploremore._compact(summary(2))]}
    fetched = {**xploremore._compact(detail(1)), "members": 7}
    fetched["evidence"].append({"url": "https://news.ycombinator.com/item?id=99", "platform": "hn", "excerpt": "x"})
    return [
        AIMessage(content="", tool_calls=[{"name": "find_problems", "args": {"topic": "t"}, "id": "a"}]),
        ToolMessage(content=json.dumps(listed), name="find_problems", tool_call_id="a"),
        # The MCP adapter delivers text content blocks instead of a string.
        ToolMessage(content=[{"type": "text", "text": json.dumps(fetched)}], name="get_problem", tool_call_id="b"),
        ToolMessage(content=json.dumps([{"title": "HN story"}]), name="search_hacker_news", tool_call_id="c"),
    ]


def test_observe_tool_messages_reads_both_transports_and_merges_evidence():
    ledger, unavailable = xploremore.observe_tool_messages(_tool_messages())
    assert set(ledger) == {1, 2} and unavailable == []
    assert "https://news.ycombinator.com/item?id=99" in {e["url"] for e in ledger[1]["evidence"]}

    outage = [ToolMessage(content=json.dumps({"unavailable": "http_503"}), name="find_problems", tool_call_id="z")]
    assert xploremore.observe_tool_messages(outage) == ({}, ["http_503"])


def test_provenance_is_decided_by_code_not_by_the_model():
    ledger, _ = xploremore.observe_tool_messages(_tool_messages())
    report = ResearchReport(
        ideas=[
            DiscoveredIdea(title="A", description="d", source_url="https://github.com/acme/agents/issues/11", problem_id=1),
            # No id, but the source is one of problem 2's evidence posts (trailing slash tolerated).
            DiscoveredIdea(title="B", description="d", source_url="https://github.com/acme/agents/issues/21/"),
            # The model invented an id it never received.
            DiscoveredIdea(title="C", description="d", source_url="https://example.com/x", problem_id=999),
            # A forged provenance in the model output is overwritten.
            DiscoveredIdea(
                title="D",
                description="d",
                source_url="https://example.com/y",
                provenance=XploreMoreProvenance(problem_id=5, voices=500, sources=50),
            ),
        ]
    )
    a, b, c, d = xploremore.attach_provenance(report, ledger).ideas

    assert a.problem_id == 1 and a.provenance.voices == 5 and a.provenance.sources == 3
    assert a.provenance.platforms == ["github", "hn"] and len(a.provenance.evidence_urls) == 3
    assert a.provenance.card_line == "Discovered via XploreMore: 5 people across 3 sources"
    assert b.problem_id == 2 and b.provenance.problem_id == 2
    assert c.problem_id is None and c.provenance is None
    assert d.provenance is None


def test_card_line_grammar_for_one_voice():
    p = XploreMoreProvenance(problem_id=1, voices=1, sources=1)
    assert p.card_line == "Discovered via XploreMore: 1 person across 1 source"


def test_provenance_is_hidden_from_the_models_response_schema():
    schema = json.dumps(ResearchReport.model_json_schema())
    assert "problem_id" in schema and "provenance" not in schema


async def test_run_research_attaches_provenance(monkeypatch, configured):
    monkeypatch.setenv("RESEARCH_TOOLS", "in_process")
    get_settings.cache_clear()
    report = ResearchReport(
        ideas=[DiscoveredIdea(title="A", description="d", source_url="https://example.com", problem_id=2)]
    )

    async def fake_turn(tools, topic):
        assert {t.name for t in tools} >= xploremore.TOOL_NAMES
        return {"messages": _tool_messages(), "structured_response": report}

    async def no_usage(*args, **kwargs):
        return None

    monkeypatch.setattr(research, "_run_turn", fake_turn)
    monkeypatch.setattr(research.cost_tracking, "record_usage", no_usage)
    result = await research.run_research("agent tooling")
    assert result.ideas[0].provenance.problem_id == 2


async def test_mcp_outages_are_mirrored_into_the_local_breaker(monkeypatch, configured):
    outage = [ToolMessage(content=json.dumps({"unavailable": "http_503"}), name="find_problems", tool_call_id="z")]

    async def fake_tools():
        return [], "mcp"

    async def fake_turn(tools, topic):
        return {"messages": outage, "structured_response": ResearchReport()}

    async def no_usage(*args, **kwargs):
        return None

    monkeypatch.setattr(research, "_research_tools", fake_tools)
    monkeypatch.setattr(research, "_run_turn", fake_turn)
    monkeypatch.setattr(research.cost_tracking, "record_usage", no_usage)
    await research.run_research("t")
    assert xploremore.breaker().failures == 1


# --- downstream: analyst, dedupe, persistence, API -------------------------------------


def _provenance() -> XploreMoreProvenance:
    return XploreMoreProvenance(
        problem_id=42, voices=23, sources=5, platforms=["github", "hn"], demand=4.2, evidence_urls=["https://e/1"]
    )


def test_analyst_prompt_adds_measured_demand_only_with_provenance():
    plain = DiscoveredIdea(title="T", description="D", source_url="https://s")
    assert analyst.score_prompt(plain) == analyst.SCORE_PROMPT_TEMPLATE.format(title="T", description="D")

    sourced = plain.model_copy(update={"problem_id": 42, "provenance": _provenance()})
    prompt = analyst.score_prompt(sourced)
    assert prompt.startswith(analyst.score_prompt(plain))
    assert "23 distinct people across 5 sources (github, hn)" in prompt


async def test_same_xploremore_problem_is_a_duplicate_by_identity(monkeypatch):
    async def allowed(text):
        return True

    def no_llm(role):
        raise AssertionError("a known problem must be deduped before any scoring call")

    monkeypatch.setattr(analyst, "is_idea_allowed", allowed)
    monkeypatch.setattr(analyst, "get_chat_model", no_llm)
    monkeypatch.setattr(analyst, "find_problem_duplicate", lambda pid: "idea-7" if pid == 42 else None)
    monkeypatch.setattr(analyst, "find_duplicate", lambda text: None)

    idea = DiscoveredIdea(title="Worded differently", description="d", source_url="https://s", problem_id=42)
    result = await analyst.analyze_idea(idea.model_copy(update={"provenance": _provenance()}))
    assert result.status == "duplicate" and "idea-7" in result.reasoning
    assert result.provenance.problem_id == 42


def test_memory_remembers_problem_ids(tmp_path, monkeypatch):
    from p2pops import memory

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    memory._get_collection.cache_clear()
    try:
        assert memory.find_problem_duplicate(42) is None
        memory.remember("idea-plain", "An unrelated idea about calendars")
        memory.remember("idea-xm", "Tool calls drop nested arguments", problem_id=42)
        assert memory.find_problem_duplicate(42) == "idea-xm"
        assert memory.find_problem_duplicate(43) is None
    finally:
        memory._get_collection.cache_clear()
        get_settings.cache_clear()


async def test_provenance_persists_to_ideas_and_the_showcase(db):
    run = await repo.create_run("t")
    sourced = make_idea().model_copy(update={"problem_id": 42, "provenance": _provenance()})
    row = await repo.save_idea(sourced, run_id=run.id)
    await repo.save_idea(make_idea(title="Plain"), run_id=run.id)

    items = {i["title"]: i for i in await repo.showcase_items()}
    card = items["Test problem"]["provenance"]
    assert card["problem_id"] == 42 and card["voices"] == 23
    assert card["card_line"] == "Discovered via XploreMore: 23 people across 5 sources"
    assert items["Plain"]["provenance"] is None

    out = IdeaOut.model_validate(await repo.get_idea(row.id))
    assert out.xploremore_problem_id == 42 and out.provenance.sources == 5
    assert repo.provenance_out("{not json") is None
