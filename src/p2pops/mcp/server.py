"""MCP server exposing the Research Agent's discovery tools.

Run standalone with `uv run python -m p2pops.mcp.server` (stdio transport) so
any MCP-compatible client -- this project's own Research Agent, or an
external one such as Claude Desktop -- can call these tools directly.

Payload sizes are capped here, not just given conservative defaults: a
multi-turn tool-calling agent resends its *entire* message history on every
turn, so a few generous tool results compound fast. A live run against
Groq's on-demand gpt-oss-20b tier (8000 tokens/minute) hit a hard 413 --
not a transient rate limit, but a single request permanently too large for
the ceiling -- after just one search and two article reads. These caps are
sized to keep a full research turn comfortably inside that kind of budget,
which is also just good hygiene against any provider's limits.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from p2pops.tools import xploremore
from p2pops.tools.hn import search_hn
from p2pops.tools.web import fetch_article_text
from p2pops.tools.websearch import search_web as _search_web

mcp = FastMCP("p2pops-research")

MAX_SEARCH_RESULTS = 6
MAX_ARTICLE_CHARS = 1200


@mcp.tool()
def search_hacker_news(query: str, limit: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search Hacker News for stories matching `query`.

    Never returns a bare empty list on zero matches: langchain-mcp-adapters
    maps MCP content blocks one-to-one from the return value, so an empty
    Python list becomes a ToolMessage with *zero* content blocks -- which
    Groq's chat-completions endpoint rejects outright (a live run hit this
    exact 400: "messages.N.content: minimum number of items is 1"). A
    one-item placeholder keeps the tool result meaningful and always
    provider-safe.
    """
    capped_limit = min(limit, MAX_SEARCH_RESULTS)
    stories = [story.model_dump() for story in search_hn(query, limit=capped_limit)]
    return stories or [{"info": f"No Hacker News results found for '{query}'."}]


@mcp.tool()
def search_web(query: str, limit: int = MAX_SEARCH_RESULTS) -> list[dict]:
    """Search the general web (beyond Hacker News) for pages matching
    `query` — blogs, forums, docs, issue trackers, anywhere indexed.

    Same non-empty-return rule as search_hacker_news: an empty MCP content
    list is rejected outright by some providers, so zero matches (or a
    search backend hiccup) yields an explicit one-item placeholder.
    """
    capped_limit = min(limit, MAX_SEARCH_RESULTS)
    results = [result.model_dump() for result in _search_web(query, limit=capped_limit)]
    return results or [{"info": f"No web results found for '{query}'."}]


@mcp.tool()
def read_article(url: str) -> str:
    """Fetch and return the readable text of an external article URL, capped
    to a length that keeps a multi-tool-call agent turn inside tight
    provider rate limits."""
    return fetch_article_text(url, max_chars=MAX_ARTICLE_CHARS)


@mcp.tool()
async def find_problems(
    topic: str,
    category: xploremore.Category | None = None,
    since_days: int = 30,
    min_voices: int = 2,
    limit: int = 5,
) -> dict[str, Any]:
    """Find real problems people report (HN, GitHub issues, Lobsters, Stack
    Exchange), already clustered and ranked by demand by XploreMore. Each has
    an id, voices (distinct people), sources and evidence URLs.

    Same function the in-process transport binds (tools/xploremore.py, ADR-0012):
    unconfigured, rate-limited or failing XploreMore yields an explicit
    "unavailable" result, never an empty one."""
    return await xploremore.find_problems(topic, category, since_days, min_voices, limit)


@mcp.tool()
async def get_problem(problem_id: int, evidence: int = 3) -> dict[str, Any]:
    """Get one XploreMore problem by id with more evidence posts and its
    demand breakdown."""
    return await xploremore.get_problem(problem_id, evidence)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
