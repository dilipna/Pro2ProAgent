import sys

import pytest
from langchain_mcp_adapters.client import MultiServerMCPClient

from p2pops.mcp.server import search_hacker_news


@pytest.mark.asyncio
async def test_mcp_server_exposes_expected_tools():
    client = MultiServerMCPClient(
        {
            "research": {
                "transport": "stdio",
                "command": sys.executable,
                "args": ["-m", "p2pops.mcp.server"],
            }
        }
    )
    tools = await client.get_tools()
    tool_names = {tool.name for tool in tools}

    assert {"search_hacker_news", "read_article"} <= tool_names


def test_search_never_returns_a_bare_empty_list():
    """Regression test: langchain-mcp-adapters maps MCP content blocks
    one-to-one from the return value, so `[]` becomes a ToolMessage with
    zero content blocks -- which Groq's chat-completions endpoint rejects
    outright. A query guaranteed to match nothing must still get a
    non-empty, informative placeholder back."""
    result = search_hacker_news("xyzzy_definitely_no_hn_stories_match_this_qqq", limit=3)

    assert isinstance(result, list)
    assert len(result) >= 1
