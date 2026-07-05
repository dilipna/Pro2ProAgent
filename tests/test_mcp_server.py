import sys

import pytest
from langchain_mcp_adapters.client import MultiServerMCPClient


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
