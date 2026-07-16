"""Research Agent tool transport: in-process by default-safe fallback.

The MCP stdio subprocess hangs forever inside the API event loop on the
Linux prod host; these tests lock in the in-process path and the automatic
degradation so a run can never stall at research again.
"""

import pytest

from p2pops.agents import research
from p2pops.config import get_settings


@pytest.fixture(autouse=True)
def _reset_breaker(monkeypatch):
    monkeypatch.setattr(research, "_mcp_unhealthy", False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_in_process_tools_mirror_the_mcp_names():
    names = {t.name for t in research._in_process_tools()}
    assert names == {"search_hacker_news", "search_web", "read_article"}


async def test_hn_tool_never_returns_a_bare_empty_list(monkeypatch):
    """Same provider-safety contract as the MCP server: empty results must
    still yield a non-empty, informative placeholder (Groq rejects a
    tool-result message with zero content blocks)."""
    monkeypatch.setattr(research, "search_hn", lambda *a, **k: [])
    result = await research._search_hacker_news("nothing matches this")
    assert isinstance(result, list) and len(result) >= 1


async def test_selects_in_process_when_configured(monkeypatch):
    monkeypatch.setenv("RESEARCH_TOOLS", "in_process")
    get_settings.cache_clear()

    async def _boom():
        raise AssertionError("MCP must not be contacted when in_process is configured")

    monkeypatch.setattr(research, "_mcp_tools", _boom)
    tools, transport = await research._research_tools()
    assert transport == "in-process"
    assert {t.name for t in tools} == {"search_hacker_news", "search_web", "read_article"}


async def test_falls_back_and_trips_breaker_when_mcp_fails(monkeypatch):
    monkeypatch.setenv("RESEARCH_TOOLS", "mcp")
    get_settings.cache_clear()

    calls = {"n": 0}

    async def _fail():
        calls["n"] += 1
        raise TimeoutError("subprocess handshake never completed")

    monkeypatch.setattr(research, "_mcp_tools", _fail)

    tools, transport = await research._research_tools()
    assert transport == "in-process"
    assert research._mcp_unhealthy is True

    # Breaker is now tripped: the next run skips MCP entirely (no 2nd attempt).
    tools2, transport2 = await research._research_tools()
    assert transport2 == "in-process"
    assert calls["n"] == 1
