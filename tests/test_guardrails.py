import pytest

from p2pops.guardrails import is_idea_allowed


@pytest.mark.asyncio
async def test_guardrails_blocks_spam_and_allows_legit_idea():
    legit = (
        "Developers can't figure out why their LangGraph agent silently drops "
        "tool call results with no trace context to debug from."
    )
    spam = "buy cheap watches now click here!!! www.spam.example"

    assert await is_idea_allowed(legit) is True
    assert await is_idea_allowed(spam) is False
