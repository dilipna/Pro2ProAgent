"""Analyst Agent: guardrails, dedupes, and scores one discovered idea.

Compute-only — persistence and memory writes belong to the orchestration
layer (graph nodes), so the agent stays a pure `DiscoveredIdea ->
AnalyzedIdea` transform that is trivial to evaluate in isolation.
"""

import logfire

from p2pops import cost_tracking
from p2pops.chat_model import get_chat_model
from p2pops.guardrails import is_idea_allowed
from p2pops.memory import find_duplicate, find_problem_duplicate
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


def score_prompt(idea: DiscoveredIdea) -> str:
    """The scoring prompt, plus measured demand when the idea came from
    XploreMore. Ideas without provenance get the exact original prompt, so
    the promptfoo scenarios keep testing the same text."""
    prompt = SCORE_PROMPT_TEMPLATE.format(title=idea.title, description=idea.description)
    p = idea.provenance
    if p is None:
        return prompt
    platforms = ", ".join(p.platforms) or "unknown platforms"
    return (
        f"{prompt}\nMeasured demand (counted by XploreMore from public posts, not estimated): "
        f"{p.voices} distinct people across {p.sources} sources ({platforms})."
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

        # An idea for an XploreMore problem we already hold is a duplicate by
        # identity, however differently the model worded it this time.
        duplicate_id = None
        if idea.problem_id is not None:
            duplicate_id = find_problem_duplicate(idea.problem_id)
        duplicate_id = duplicate_id or find_duplicate(combined_text)
        if duplicate_id:
            return AnalyzedIdea(
                **idea.model_dump(),
                status="duplicate",
                reasoning=f"Near-duplicate of existing idea {duplicate_id}",
            )

        async def score() -> IdeaVerdict:
            model = get_chat_model("default").with_structured_output(IdeaVerdict, include_raw=True)
            # See venture/agents.py::_structured for why parsing_error/None
            # must be re-raised rather than silently returned -- same
            # retry-on-malformed-output contract applies here.
            result = await model.ainvoke(score_prompt(idea))
            if result.get("parsing_error") is not None:
                raise result["parsing_error"]
            verdict = result.get("parsed")
            if verdict is None:
                raise ValueError("analyst.scorer: structured output returned no parsed result")
            await cost_tracking.record_usage("analyst.scorer", "default", result.get("raw"))
            return verdict

        verdict: IdeaVerdict = await with_retry(score, agent="analyst.scorer")

        status = "shortlisted" if verdict.score >= SHORTLIST_THRESHOLD else "rejected"
        return AnalyzedIdea(
            **idea.model_dump(),
            score=verdict.score,
            reasoning=verdict.reasoning,
            status=status,
        )
