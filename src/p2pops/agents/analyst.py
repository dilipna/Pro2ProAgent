"""Analyst Agent: guardrails, dedupes, and scores ideas the Research Agent found.

Not a LangGraph tool-calling agent like Research -- this is a classic
pipeline stage (guardrail check -> dedupe check -> structured scoring call),
which is the honest shape for this kind of work. It's still wired into the
Supervisor graph as its own node, and every step is traced.
"""

import logfire

from p2pops.chat_model import get_chat_model
from p2pops.guardrails import is_idea_allowed
from p2pops.memory import find_duplicate, remember
from p2pops.models import AnalyzedIdea, DiscoveredIdea, IdeaVerdict
from p2pops.store import save_idea

SHORTLIST_THRESHOLD = 50

SCORE_PROMPT_TEMPLATE = (
    "Score how worth building a product for this problem, from 0 (not worth "
    "it at all) to 100 (extremely worth it). Consider how specific and "
    "painful the problem is, how many people likely share it, and whether "
    "it's feasible to build a focused solution for it.\n\n"
    "Title: {title}\nDescription: {description}"
)


async def analyze_idea(idea: DiscoveredIdea) -> AnalyzedIdea:
    """Runs one discovered idea through guardrails, dedupe, and scoring, and persists it."""
    combined_text = f"{idea.title}\n{idea.description}"

    with logfire.span("agent.analyst", title=idea.title):
        if not await is_idea_allowed(combined_text):
            analyzed = AnalyzedIdea(
                **idea.model_dump(), status="rejected", reasoning="Blocked by guardrails"
            )
            save_idea(analyzed)
            return analyzed

        duplicate_id = find_duplicate(combined_text)
        if duplicate_id:
            analyzed = AnalyzedIdea(
                **idea.model_dump(),
                status="duplicate",
                reasoning=f"Near-duplicate of existing idea {duplicate_id}",
            )
            save_idea(analyzed)
            return analyzed

        model = get_chat_model("default").with_structured_output(IdeaVerdict)
        verdict: IdeaVerdict = await model.ainvoke(
            SCORE_PROMPT_TEMPLATE.format(title=idea.title, description=idea.description)
        )

        status = "shortlisted" if verdict.score >= SHORTLIST_THRESHOLD else "rejected"
        analyzed = AnalyzedIdea(
            **idea.model_dump(),
            score=verdict.score,
            reasoning=verdict.reasoning,
            status=status,
        )
        idea_id = save_idea(analyzed)
        remember(idea_id, combined_text)
        return analyzed


async def analyze_ideas(ideas: list[DiscoveredIdea]) -> list[AnalyzedIdea]:
    return [await analyze_idea(idea) for idea in ideas]
