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
import logging
import sys

import logfire
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from p2pops import cost_tracking
from p2pops.chat_model import get_chat_model
from p2pops.config import get_settings
from p2pops.models import ResearchReport
from p2pops.resilience import with_retry
from p2pops.telemetry import configure_telemetry
from p2pops.tools.hn import search_hn
from p2pops.tools.web import fetch_article_text
from p2pops.tools.websearch import search_web as _search_web

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM_PROMPT = (
    "You are the Research Agent for P2POps, an AI company that finds real, "
    "unsolved AI-related problems people are complaining about online. Use "
    "the search_hacker_news tool to find relevant discussions, search_web "
    "to look beyond Hacker News (blogs, forums, docs, issue trackers -- "
    "anywhere on the web), and read_article to pull in the full text of a "
    "linked page when the title alone isn't enough context. Report back a "
    "short list of concrete, specific problems -- not vague trends -- each "
    "with a title, a one-line description, and the source URL.\n\n"
    "Every reported idea MUST have a real, non-empty source_url copied "
    "exactly from a search result's hn_url or url field. If a point you "
    "want to make (e.g. a pattern spanning several discussions) doesn't "
    "trace back to one specific result, do not report it as its own idea -- "
    "fold it into the description of an idea that does have a source, or "
    "leave it out. Never output null or a placeholder for source_url.\n\n"
    "Budget your tool calls: call search_hacker_news exactly once, call "
    "search_web at most once (do it when HN results are thin or the topic "
    "lives outside HN's usual orbit), then read_article on at most ONE of "
    "the most promising results. Do not search again or read more articles "
    "-- result titles and snippets are almost always enough signal."
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
# made 4 tool calls despite the prompt, which alone needs 10 steps. 16 gave
# headroom for that realistic variance (up to ~7 tool calls) while still
# stopping a genuinely runaway loop well short of exhausting the rate-limit
# budget the payload caps (MAX_SEARCH_RESULTS/MAX_ARTICLE_CHARS) protect.
# Raised to 18 when search_web joined the toolset: the sanctioned maximum
# path grew by one tool call (2 steps); the same variance margin applies.
MAX_RESEARCH_STEPS = 18


# The three tools are the same non-empty-return-safe contracts the MCP
# server (mcp/server.py) exposes -- same names (the system prompt references
# them by name), same caps, same empty-list placeholders that keep Groq's
# chat-completion schema happy. Defined once here so the in-process transport
# and the MCP server can't drift apart.
_MAX_SEARCH_RESULTS = 6
_MAX_ARTICLE_CHARS = 1200


async def _search_hacker_news(query: str, limit: int = _MAX_SEARCH_RESULTS) -> list[dict]:
    """Search Hacker News for stories matching `query`."""
    capped = min(limit, _MAX_SEARCH_RESULTS)
    stories = [s.model_dump() for s in await asyncio.to_thread(search_hn, query, capped)]
    return stories or [{"info": f"No Hacker News results found for '{query}'."}]


async def _search_web_tool(query: str, limit: int = _MAX_SEARCH_RESULTS) -> list[dict]:
    """Search the general web (blogs, forums, docs, issue trackers) for `query`."""
    capped = min(limit, _MAX_SEARCH_RESULTS)
    results = [r.model_dump() for r in await asyncio.to_thread(_search_web, query, capped)]
    return results or [{"info": f"No web results found for '{query}'."}]


async def _read_article(url: str) -> str:
    """Fetch and return the readable text of an external article URL."""
    return await asyncio.to_thread(fetch_article_text, url, _MAX_ARTICLE_CHARS)


def _in_process_tools() -> list[StructuredTool]:
    """The research tools bound directly, no subprocess. This is the
    production-default transport: spawning the MCP stdio server as a
    subprocess *per tool call* from inside the API's asyncio event loop
    hangs indefinitely on the Linux host (SelectorEventLoop, no uvloop) --
    reproduced live in prod, every run stalled at research/stage_started
    forever. Calling the identical functions in-process removes that whole
    failure mode; the tools flow through the exact same Guardrail -> dedupe
    -> Analyst chain, so nothing about quality changes. See ADR-0011."""
    return [
        StructuredTool.from_function(coroutine=_search_hacker_news, name="search_hacker_news"),
        StructuredTool.from_function(coroutine=_search_web_tool, name="search_web"),
        StructuredTool.from_function(coroutine=_read_article, name="read_article"),
    ]


def _mcp_server_config() -> dict:
    return {
        "research": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "p2pops.mcp.server"],
        }
    }


# Process-level circuit breaker: once the MCP transport has proven unusable
# in this environment, stop paying the (long) timeout on every subsequent
# run and go straight to the in-process tools.
_mcp_unhealthy = False


async def _mcp_tools() -> list:
    """Fetch tools from the MCP stdio server, bounded by a timeout so a
    subprocess that never completes its handshake can't hang the caller."""
    settings = get_settings()
    client = MultiServerMCPClient(_mcp_server_config())
    return await asyncio.wait_for(client.get_tools(), timeout=settings.mcp_startup_timeout_s)


async def _research_tools() -> tuple[list, str]:
    """(tools, transport_label). Honors the configured transport, but always
    degrades to in-process rather than failing -- the discovery pipeline must
    produce ideas even where the MCP subprocess can't run."""
    global _mcp_unhealthy
    settings = get_settings()
    if settings.research_tools != "mcp" or _mcp_unhealthy:
        return _in_process_tools(), "in-process"
    try:
        return await _mcp_tools(), "mcp"
    except Exception as exc:
        _mcp_unhealthy = True
        logger.warning("MCP research tools unavailable (%s); using in-process tools", exc)
        return _in_process_tools(), "in-process"


def _build_agent(tools: list):
    return create_react_agent(
        get_chat_model("default"),
        tools,
        prompt=RESEARCH_SYSTEM_PROMPT,
        response_format=ResearchReport,
    )


async def _run_turn(tools: list, topic: str) -> dict:
    agent = _build_agent(tools)
    settings = get_settings()

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

    # A 429 mid-loop retries the whole agent turn -- tool calls (HN
    # search/read) are idempotent, so the only cost is repeated work, never
    # incorrect results. The outer wait_for is a hard ceiling: no transport,
    # however wedged, can leave a run stuck "running" forever again.
    return await asyncio.wait_for(
        with_retry(call, agent="research"), timeout=settings.research_turn_timeout_s
    )


async def run_research(topic: str) -> ResearchReport:
    """Run the Research Agent end to end for a given topic and return a
    structured report. Tries the configured transport first, then falls back
    to in-process tools if it fails or times out -- so a broken MCP subprocess
    degrades to a slower-but-working run instead of an eternal stall."""
    global _mcp_unhealthy
    tools, transport = await _research_tools()
    with logfire.span("agent.research", topic=topic, transport=transport):
        try:
            result = await _run_turn(tools, topic)
        except Exception as exc:
            if transport != "mcp":
                raise
            # The MCP handshake succeeded but a per-call subprocess spawn hung
            # (or otherwise failed): trip the breaker and retry in-process so
            # this run still produces ideas.
            _mcp_unhealthy = True
            logger.warning("MCP research turn failed (%s); retrying in-process", exc)
            with logfire.span("agent.research.fallback", topic=topic):
                result = await _run_turn(_in_process_tools(), topic)

    # Unlike the single structured-output call sites (venture/build,
    # analyst), a ReAct turn makes one LLM call per tool-calling step -- so
    # usage is captured per message here rather than once per call, giving
    # one LlmCall row per actual model turn instead of one aggregated guess.
    for message in result.get("messages", []):
        await cost_tracking.record_usage("research", "default", message)

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
