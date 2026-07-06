"""Venture pipeline agents.

Contracts are uniform across agents:
- Input: the idea + the deterministic evidence bundle (+ upstream artifacts).
- Output: exactly one structured schema from `schemas.py` — never free text.
- Reliability: temperature 0, bounded retry (transient failures only),
  clamping validators absorb mildly out-of-range scores.
- Communication: downstream agents receive upstream artifacts verbatim in
  their prompt context; the refiner receives the red team's findings and
  must answer each one — that is the agents-talking-to-agents loop, in a
  form that stays traceable.

`_structured()` is the single seam through which every LLM call flows:
tests substitute it to run the whole graph deterministically offline.
"""

import asyncio
import logging

import logfire
from pydantic import BaseModel

from ..chat_model import get_chat_model
from ..tools.hn import search_hn
from ..tools.web import fetch_article_text
from .principles import principles_digest
from .schemas import (
    CompetitorLandscape,
    DemandAssessment,
    DirectionSlate,
    EvidenceBundle,
    EvidenceItem,
    ProblemValidation,
    ProductVision,
    RefinedDirection,
    SegmentAnalysis,
    SolutionDirection,
    StressTestReport,
)

logger = logging.getLogger(__name__)

_RETRIES = 2
_RETRY_DELAY_S = 2.0


async def _structured[T: BaseModel](
    schema: type[T],
    prompt: str,
    *,
    agent: str,
    tier: str = "default",
    max_tokens: int = 2048,
) -> T:
    """One retried, traced, structured LLM call. The test seam."""
    last_error: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            with logfire.span("venture.llm", agent=agent, schema=schema.__name__, attempt=attempt):
                model = get_chat_model(tier, max_tokens=max_tokens, temperature=0.0)
                return await model.with_structured_output(schema).ainvoke(prompt)
        except Exception as exc:
            last_error = exc
            logger.warning("%s attempt %d failed: %s", agent, attempt, exc)
            if attempt < _RETRIES:
                await asyncio.sleep(_RETRY_DELAY_S * attempt)
    raise RuntimeError(f"{agent} failed after {_RETRIES} attempts") from last_error


# --- Evidence gathering (deterministic, no LLM) ----------------------------------


async def gather_evidence(title: str, description: str) -> EvidenceBundle:
    """Pulls real-world evidence for the problem: HN discussions matching the
    idea, plus readable text from the top linked articles. Pure retrieval —
    the analysis agents cite it; nothing here is generated."""
    query = title[:80]
    items: list[EvidenceItem] = []

    try:
        stories = await asyncio.to_thread(search_hn, query, 8)
    except Exception as exc:
        logger.warning("HN evidence search failed: %s", exc)
        stories = []

    for story in stories:
        items.append(
            EvidenceItem(
                source="hackernews",
                title=story.title,
                url=story.hn_url,
                detail=f"{story.points} points · {story.num_comments} comments · {story.created_at[:10]}",
            )
        )

    # Enrich with full text of the two highest-signal linked articles.
    linked = [s for s in stories if s.url][:2]
    for story in linked:
        text = await asyncio.to_thread(fetch_article_text, story.url, 2500)
        if not text.startswith("(could not fetch"):
            items.append(
                EvidenceItem(source="article", title=story.title, url=story.url, detail=text)
            )

    return EvidenceBundle(query=query, items=items)


def _evidence_block(evidence: EvidenceBundle) -> str:
    if evidence.is_empty:
        return "(no external evidence retrieved — reason from the problem statement alone and lower your confidence accordingly)"
    lines = []
    for i, item in enumerate(evidence.items, 1):
        lines.append(f"[E{i}] ({item.source}) {item.title} — {item.detail[:600]} <{item.url}>")
    return "\n".join(lines)


_CONTEXT_TEMPLATE = """PROBLEM UNDER INVESTIGATION
Title: {title}
Description: {description}
Analyst's original assessment: {reasoning}

EXTERNAL EVIDENCE (cite items as E1, E2, ... in your outputs)
{evidence}
"""


def _context(title: str, description: str, reasoning: str, evidence: EvidenceBundle) -> str:
    return _CONTEXT_TEMPLATE.format(
        title=title,
        description=description,
        reasoning=reasoning or "(none)",
        evidence=_evidence_block(evidence),
    )


# --- Parallel analysis agents ------------------------------------------------------


async def validate_problem(ctx: str) -> ProblemValidation:
    """Success criteria: verdict grounded in cited evidence; counter-signals
    honestly reported; confidence reflects evidence quality, not enthusiasm."""
    return await _structured(
        ProblemValidation,
        ctx
        + "\nYou are the Problem Validator for a venture studio. Determine whether "
        "this problem is real, recurring, and important enough to build against. "
        "Base every claim on the evidence items (cite E-numbers). If evidence is "
        "thin or contradictory, say so and lower confidence — a false 'real' "
        "verdict costs the studio months. Report counter-signals even when the "
        "verdict is positive.",
        agent="venture/validator",
    )


async def analyze_segments(ctx: str) -> SegmentAnalysis:
    """Success criteria: segments are distinct and reachable; primary segment
    chosen by pain intensity x reachability, not size alone."""
    return await _structured(
        SegmentAnalysis,
        ctx
        + "\nYou are the Segment Ethnographer. Identify the distinct user segments "
        "who feel this pain, what outcome each is actually buying, and how they "
        "cope today. Pick the primary segment to build for first: the one where "
        "pain intensity and reachability multiply best. Ground segment claims in "
        "the evidence where possible.",
        agent="venture/ethnographer",
    )


async def assess_demand(ctx: str) -> DemandAssessment:
    """Success criteria: every demand signal maps to observable evidence;
    market-size reasoning is order-of-magnitude honest, never invented TAM."""
    return await _structured(
        DemandAssessment,
        ctx
        + "\nYou are the Demand Analyst. Measure urgency (need it now?), frequency "
        "(how often the pain bites), and willingness to pay (budget signals, "
        "existing spend on workarounds). List concrete demand signals tied to "
        "evidence items. For market size, give order-of-magnitude reasoning about "
        "who would pay — no fabricated TAM figures.",
        agent="venture/demand-analyst",
    )


async def scout_competitors(ctx: str) -> CompetitorLandscape:
    """Success criteria: landscape covers tools AND workarounds; the unserved
    gap is specific enough to aim a wedge at; saturation is justified."""
    return await _structured(
        CompetitorLandscape,
        ctx
        + "\nYou are the Competitor Scout. Map existing solutions to this problem — "
        "commercial products, open source, and the do-nothing workaround — with "
        "each one's concrete shortcoming (cite evidence where it shows users "
        "complaining about them). Then name the sharpest unserved gap: the wedge "
        "a new entrant could own. Rate saturation honestly.",
        agent="venture/competitor-scout",
    )


# --- Solution generation, stress testing, refinement, vision ------------------------


async def generate_directions(
    ctx: str,
    validation: ProblemValidation,
    segments: SegmentAnalysis,
    demand: DemandAssessment,
    landscape: CompetitorLandscape,
) -> DirectionSlate:
    """Success criteria: 4-6 directions that differ in APPROACH (not features);
    each applies a named principle with a transfer argument; sub-scores are
    conservative and justified; rejected framings listed."""
    upstream = (
        f"\nVALIDATION: {validation.model_dump_json()}"
        f"\nSEGMENTS: {segments.model_dump_json()}"
        f"\nDEMAND: {demand.model_dump_json()}"
        f"\nLANDSCAPE: {landscape.model_dump_json()}"
    )
    return await _structured(
        DirectionSlate,
        ctx
        + upstream
        + "\n\nVENTURE PRINCIPLE LIBRARY (apply by key, argue the transfer):\n"
        + principles_digest()
        + "\n\nYou are the Solution Architect. Generate 4-6 meaningfully different "
        "solution directions for the primary segment — different mechanisms, not "
        "one product with different names. For each: apply the single most "
        "transferable principle from the library and argue WHY it transfers to "
        "this problem's structure (and where its failure mode lurks). Aim the "
        "wedge at the landscape's unserved gap. Score the four sub-scores "
        "conservatively; 70+ needs strong evidence. List framings you considered "
        "and rejected, with reasons — do not anchor on your first idea.",
        agent="venture/architect",
        tier="builder",
        max_tokens=4096,
    )


async def stress_test(
    ctx: str, direction: SolutionDirection, refinement: RefinedDirection | None
) -> StressTestReport:
    """Success criteria: attacks from all five lenses; issues are concrete
    failure scenarios (not vague worries); severities honest; verdict follows
    from the issues."""
    current = direction.model_dump_json()
    revision = f"\nLATEST REVISION: {refinement.model_dump_json()}" if refinement else ""
    return await _structured(
        StressTestReport,
        ctx
        + f"\nCHOSEN DIRECTION: {current}{revision}"
        + "\n\nYou are the Red Team. Attack this direction from five lenses — "
        "technical, business, financial, operational, user — one concrete failure "
        "scenario at a time (who does what, and what breaks). Severity: critical "
        "= kills the opportunity if unaddressed; major = material risk; minor = "
        "friction. Propose the best real mitigation for each, or state 'none "
        "known'. Also check the applied principle's documented failure mode. "
        "Verdict must follow from your own issues: do_not_proceed if any critical "
        "issue has no credible mitigation.",
        agent="venture/red-team",
        tier="builder",
    )


async def refine_direction(
    ctx: str, direction: SolutionDirection, report: StressTestReport
) -> RefinedDirection:
    """Success criteria: every critical/major issue explicitly answered by a
    change or honestly carried as unresolved; the wedge stays narrow."""
    return await _structured(
        RefinedDirection,
        ctx
        + f"\nDIRECTION: {direction.model_dump_json()}"
        + f"\nRED TEAM REPORT: {report.model_dump_json()}"
        + "\n\nYou are the Refiner. Revise the direction so each critical and "
        "major issue is either designed away (state the change and which issue "
        "it answers) or explicitly carried as an unresolved known risk — never "
        "silently dropped. Do not broaden the wedge to dodge criticism; "
        "narrowing is usually the answer.",
        agent="venture/refiner",
        tier="builder",
    )


async def write_vision(
    ctx: str,
    direction: SolutionDirection,
    segments: SegmentAnalysis,
    landscape: CompetitorLandscape,
    refinement: RefinedDirection | None,
    unresolved: list[str],
) -> ProductVision:
    """Success criteria: a stranger understands the one-liner; positioning is
    against the real alternative (often the workaround); execution strategy
    names the wedge, channel, and first proof of value; risks carried forward."""
    revision = f"\nFINAL REVISION: {refinement.model_dump_json()}" if refinement else ""
    return await _structured(
        ProductVision,
        ctx
        + f"\nDIRECTION: {direction.model_dump_json()}{revision}"
        + f"\nSEGMENTS: {segments.model_dump_json()}"
        + f"\nLANDSCAPE: {landscape.model_dump_json()}"
        + f"\nKNOWN UNRESOLVED RISKS: {unresolved}"
        + "\n\nYou are the Product Strategist. Produce the definitive product "
        "vision for this opportunity: name, five-second one-liner, value "
        "proposition versus the user's real alternative, positioning, durable "
        "differentiation (tied to the landscape), the primary segment, a "
        "first-90-days execution strategy (wedge, channel, first proof of "
        "value), measurable success metrics, and the known risks carried "
        "forward. Write like it will be read by a skeptical founder tomorrow.",
        agent="venture/strategist",
        tier="builder",
        max_tokens=4096,
    )
