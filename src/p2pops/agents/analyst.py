"""Analyst Agent: guardrails, dedupes, and scores one discovered idea.

Compute-only — persistence and memory writes belong to the orchestration
layer (graph nodes), so the agent stays a pure `DiscoveredIdea ->
AnalyzedIdea` transform that is trivial to evaluate in isolation.
"""

import logfire

from p2pops.chat_model import get_chat_model
from p2pops.guardrails import is_idea_allowed
from p2pops.memory import find_duplicate
from p2pops.models import AnalyzedIdea, DiscoveredIdea, IdeaVerdict
from p2pops.resilience import with_retry

SHORTLIST_THRESHOLD = 50

SCORE_PROMPT_TEMPLATE = (
    "Score how worth building a product for this problem, from 0 (not worth "
    "it at all) to 100 (extremely worth it). Consider how specific and "
    "painful the problem is, how many people likely share it, and whether "
    "it's feasible to build a focused solution for it.\n\n"
    "Title: {title}\nDescription: {description}"
)


async def analyze_idea(idea: DiscoveredIdea) -> AnalyzedIdea:
    """Runs one discovered idea through guardrails, dedupe, and scoring."""
    combined_text = f"{idea.title}\n{idea.description}"

    with logfire.span("agent.analyst", title=idea.title):
        allowed = await with_retry(lambda: is_idea_allowed(combined_text), agent="analyst.guardrail")
        if not allowed:
            return AnalyzedIdea(
                **idea.model_dump(), status="rejected", reasoning="Blocked by guardrails"
            )

        duplicate_id = find_duplicate(combined_text)
        if duplicate_id:
            return AnalyzedIdea(
                **idea.model_dump(),
                status="duplicate",
                reasoning=f"Near-duplicate of existing idea {duplicate_id}",
            )

        async def score():
            model = get_chat_model("default").with_structured_output(IdeaVerdict)
            return await model.ainvoke(
                SCORE_PROMPT_TEMPLATE.format(title=idea.title, description=idea.description)
            )

        verdict: IdeaVerdict = await with_retry(score, agent="analyst.scorer")

        status = "shortlisted" if verdict.score >= SHORTLIST_THRESHOLD else "rejected"
        return AnalyzedIdea(
            **idea.model_dump(),
            score=verdict.score,
            reasoning=verdict.reasoning,
            status=status,
        )
