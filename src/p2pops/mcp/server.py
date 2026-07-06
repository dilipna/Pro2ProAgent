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

from mcp.server.fastmcp import FastMCP

from p2pops.tools.hn import search_hn
from p2pops.tools.web import fetch_article_text

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
def read_article(url: str) -> str:
    """Fetch and return the readable text of an external article URL, capped
    to a length that keeps a multi-tool-call agent turn inside tight
    provider rate limits."""
    return fetch_article_text(url, max_chars=MAX_ARTICLE_CHARS)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
