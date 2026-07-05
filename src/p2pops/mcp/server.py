"""MCP server exposing the Research Agent's discovery tools.

Run standalone with `uv run python -m p2pops.mcp.server` (stdio transport) so
any MCP-compatible client -- this project's own Research Agent, or an
external one such as Claude Desktop -- can call these tools directly.
"""

from mcp.server.fastmcp import FastMCP

from p2pops.tools.hn import search_hn
from p2pops.tools.web import fetch_article_text

mcp = FastMCP("p2pops-research")


@mcp.tool()
def search_hacker_news(query: str, limit: int = 10) -> list[dict]:
    """Search Hacker News for stories matching `query`."""
    return [story.model_dump() for story in search_hn(query, limit=limit)]


@mcp.tool()
def read_article(url: str) -> str:
    """Fetch and return the readable text of an external article URL."""
    return fetch_article_text(url)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
