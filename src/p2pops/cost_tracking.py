"""Best-effort LLM cost capture -- the single seam every structured-output
call site (venture/build's `_structured`, the Analyst's scorer, the Research
Agent) flows through to record token usage.

Deliberately best-effort: a DB hiccup while recording cost must never break
the agent pipeline whose behavior is the actual product. Failures are
logged and swallowed, mirroring how `RunEvent` logging elsewhere in this
codebase is observability, not a control-flow dependency.
"""

import logging

from . import pricing
from .chat_model import resolve_model
from .db import repository as repo

logger = logging.getLogger(__name__)


async def record_usage(agent: str, tier: str, raw_message: object) -> None:
    usage = pricing.extract_usage(raw_message)
    if usage is None:
        return
    provider, model = resolve_model(tier)  # type: ignore[arg-type]
    cost = pricing.estimate_cost_usd(provider, model, usage)
    try:
        await repo.record_llm_call(
            agent=agent,
            provider=provider,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=cost,
        )
    except Exception:
        logger.warning("cost tracking: failed to record usage for %s", agent, exc_info=True)
