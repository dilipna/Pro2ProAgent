import pytest

from p2pops.config import get_settings
from p2pops.guardrails import is_idea_allowed

# These are LIVE tests: the NeMo rail's self-check is itself an LLM call, so
# they only run where a provider key is configured (a developer machine with
# .env). ci.yml is keyless by design — zero LLM calls, zero cost — so there
# these skip instead of failing, same "degrade honestly" pattern as
# promptfoo.yml. (This exact test was the silent CI-red culprit: it had no
# skip guard and failed on every keyless runner.)
requires_llm = pytest.mark.skipif(
    get_settings().active_api_key is None,
    reason="live guardrail checks need a configured LLM provider key; ci.yml is keyless by design",
)


@requires_llm
@pytest.mark.asyncio
async def test_guardrails_blocks_spam_and_allows_legit_idea():
    legit = (
        "Developers can't figure out why their LangGraph agent silently drops "
        "tool call results with no trace context to debug from."
    )
    spam = "buy cheap watches now click here!!! www.spam.example"

    assert await is_idea_allowed(legit) is True
    assert await is_idea_allowed(spam) is False

