"""Research Agent: reasons over HN/article tools served via MCP to surface
candidate AI-related problems worth shortlisting.

Unlike the plain LiteLLM-routed calls in llm.py, this agent gets its chat
model from chat_model.get_chat_model() -- LangGraph's tool-calling loop
(create_react_agent) needs a LangChain chat model with native tool binding,
which LiteLLM's LangChain shim doesn't reliably support yet. LangSmith/Logfire
still trace every step either way.
"""

import argparse
import asyncio
import sys

import logfire
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from p2pops.chat_model import get_chat_model
from p2pops.config import get_settings
from p2pops.models import ResearchReport
from p2pops.telemetry import configure_telemetry

RESEARCH_SYSTEM_PROMPT = (
    "You are the Research Agent for P2POps, an AI company that finds real, "
    "unsolved AI-related problems people are complaining about online. Use "
    "the search_hacker_news tool to find relevant discussions, and "
    "read_article to pull in the full text of a linked article when the "
    "title alone isn't enough context. Report back a short list of concrete, "
    "specific problems -- not vague trends -- each with a title, a one-line "
    "description, and the source URL."
)


def _mcp_server_config() -> dict:
    return {
        "research": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "p2pops.mcp.server"],
        }
    }


async def run_research(topic: str) -> ResearchReport:
    """Run the Research Agent end to end for a given topic and return a structured report."""
    client = MultiServerMCPClient(_mcp_server_config())
    tools = await client.get_tools()

    model = get_chat_model("default")
    agent = create_react_agent(
        model,
        tools,
        prompt=RESEARCH_SYSTEM_PROMPT,
        response_format=ResearchReport,
    )

    with logfire.span("agent.research", topic=topic):
        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Find AI-related problems people are discussing about: {topic}",
                    }
                ]
            }
        )
    return result["structured_response"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the P2POps Research Agent once.")
    parser.add_argument("topic", nargs="?", default="AI agent tooling", help="Topic to research")
    args = parser.parse_args()

    configure_telemetry()
    settings = get_settings()
    if not settings.active_api_key:
        print(
            f"No API key set for provider '{settings.llm_provider}' - the Research "
            "Agent needs it to reason. Add it to .env."
        )
        return

    report = asyncio.run(run_research(args.topic))
    if not report.ideas:
        print("No ideas found.")
        return
    for idea in report.ideas:
        print(f"- {idea.title}\n  {idea.description}\n  {idea.source_url}\n")


if __name__ == "__main__":
    main()
