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
from p2pops.resilience import with_retry
from p2pops.telemetry import configure_telemetry

RESEARCH_SYSTEM_PROMPT = (
    "You are the Research Agent for P2POps, an AI company that finds real, "
    "unsolved AI-related problems people are complaining about online. Use "
    "the search_hacker_news tool to find relevant discussions, and "
    "read_article to pull in the full text of a linked article when the "
    "title alone isn't enough context. Report back a short list of concrete, "
    "specific problems -- not vague trends -- each with a title, a one-line "
    "description, and the source URL.\n\n"
    "Every reported idea MUST have a real, non-empty source_url copied "
    "exactly from a search result's hn_url or url field. If a point you "
    "want to make (e.g. a pattern spanning several discussions) doesn't "
    "trace back to one specific result, do not report it as its own idea -- "
    "fold it into the description of an idea that does have a source, or "
    "leave it out. Never output null or a placeholder for source_url.\n\n"
    "Budget your tool calls: call search_hacker_news exactly once, then "
    "read_article on at most ONE of the most promising results. Do not "
    "search again or read more articles -- the search results' titles and "
    "point/comment counts are almost always enough signal on their own."
)

# Hard ceiling on tool-calling turns, independent of what the prompt asks
# for -- a live run on Groq's on-demand gpt-oss-20b tier (8000 tokens/min,
# shared across the whole org) showed that an open-ended ReAct loop can
# exceed a tight provider budget well before the model chooses to stop on
# its own. Research doesn't need many turns to produce a good report, so
# this costs nothing on generous providers and prevents runaway loops on
# stingy ones.
#
# Sizing this is a real trade-off, not a guess: the mandatory minimum path
# (one search, one article read, the model's final answer, then a required
# `generate_structured_response` step from `response_format`) is already 6
# LangGraph super-steps -- and LangGraph treats "reached the limit" as an
# error even when the very next step would have been the stop condition, so
# a limit of exactly 6 still trips. On top of that, a small model like
# gpt-oss-20b doesn't reliably obey "call search exactly once" -- a live run
# made 4 tool calls despite the prompt, which alone needs 10 steps. 16 gives
# headroom for that realistic variance (up to ~7 tool calls) while still
# stopping a genuinely runaway loop well short of exhausting the rate-limit
# budget the payload caps (MAX_SEARCH_RESULTS/MAX_ARTICLE_CHARS) protect.
MAX_RESEARCH_STEPS = 16


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

    async def call():
        return await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Find AI-related problems people are discussing about: {topic}",
                    }
                ]
            },
            config={"recursion_limit": MAX_RESEARCH_STEPS},
        )

    with logfire.span("agent.research", topic=topic):
        # A 429 mid-loop retries the whole agent turn -- tool calls (HN
        # search/read) are idempotent, so the only cost is repeated work,
        # never incorrect results.
        result = await with_retry(call, agent="research")
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
