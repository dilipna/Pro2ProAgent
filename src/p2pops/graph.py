"""Top-level Supervisor graph: routes discovered ideas from the Research
Agent to the Analyst Agent, or straight to END if nothing was found. This is
the org chart the rest of the pipeline hangs off of -- Milestone 4 adds a
human-review node between Analyst and END, Milestone 5 adds the build squad
subgraph after approval.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .agents.analyst import analyze_ideas
from .agents.research import run_research
from .models import AnalyzedIdea, DiscoveredIdea


class PipelineState(TypedDict):
    topic: str
    ideas: list[DiscoveredIdea]
    shortlist: list[AnalyzedIdea]


async def research_node(state: PipelineState) -> dict:
    report = await run_research(state["topic"])
    return {"ideas": report.ideas}


def supervisor_node(state: PipelineState) -> dict:
    """No-op today -- exists as the seam where routing logic grows (e.g.
    re-running Research with a narrower topic if too few ideas came back).
    """
    return {}


def route_after_supervisor(state: PipelineState) -> str:
    return "analyst" if state["ideas"] else END


async def analyst_node(state: PipelineState) -> dict:
    analyzed = await analyze_ideas(state["ideas"])
    return {"shortlist": analyzed}


def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("research", research_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("analyst", analyst_node)

    graph.add_edge(START, "research")
    graph.add_edge("research", "supervisor")
    graph.add_conditional_edges("supervisor", route_after_supervisor, {"analyst": "analyst", END: END})
    graph.add_edge("analyst", END)

    return graph.compile()


async def run_pipeline(topic: str) -> PipelineState:
    pipeline = build_pipeline()
    return await pipeline.ainvoke({"topic": topic, "ideas": [], "shortlist": []})
