"""Curated venture pattern library.

Distilled, evidence-backed patterns from companies that turned observed
pain into category-defining products. The Solution Architect cites these by
name when proposing directions, and the Red Team uses the failure modes as
attack vectors — so "learn from successful founders" is a deterministic,
explainable corpus rather than an unauditable vibe.

Each entry: the principle behind the win (not the surface product), the
conditions under which it transfers, and the classic way it fails when
misapplied.
"""

from pydantic import BaseModel


class VenturePrinciple(BaseModel):
    key: str
    company: str
    principle: str
    when_applicable: str
    failure_mode: str


PRINCIPLES: list[VenturePrinciple] = [
    VenturePrinciple(
        key="unlock-latent-supply",
        company="Airbnb / Uber",
        principle=(
            "Value already exists but is locked behind trust and coordination costs. "
            "Build the trust layer (identity, reviews, payments, insurance) and the "
            "locked supply becomes a market."
        ),
        when_applicable=(
            "The pain involves unused capacity or expertise that owners would share "
            "if risk and friction were removed."
        ),
        failure_mode=(
            "Building the marketplace before proving either side shows up; trust "
            "features nobody asked for on top of supply nobody offered."
        ),
    ),
    VenturePrinciple(
        key="collapse-integration-friction",
        company="Stripe",
        principle=(
            "When incumbents force days of setup, paperwork, or glue code, make the "
            "same capability usable in minutes by the person who feels the pain "
            "(often a developer), and let adoption climb bottom-up."
        ),
        when_applicable=(
            "Users describe an existing capability as 'possible but miserable to "
            "wire up'; the buyer and the sufferer are different people."
        ),
        failure_mode=(
            "Simplifying the demo path but not the production path — the 'seven "
            "lines of code' must stay true at scale or trust collapses."
        ),
    ),
    VenturePrinciple(
        key="democratize-the-pro-tool",
        company="Canva / Figma",
        principle=(
            "Take a workflow gated behind expert tools and retraining, and rebuild "
            "it around the non-expert's mental model — with collaboration native, "
            "not bolted on."
        ),
        when_applicable=(
            "The affected segment currently borrows time from a scarce expert (a "
            "designer, an analyst, an ops engineer) for routine cases."
        ),
        failure_mode=(
            "Dumbing down instead of re-modeling: experts reject it and novices "
            "still can't produce professional output, so nobody champions it."
        ),
    ),
    VenturePrinciple(
        key="productize-the-workaround",
        company="Slack / Shopify",
        principle=(
            "When many teams independently build the same internal duct-tape "
            "(scripts, spreadsheets, wikis), the workaround IS the product spec — "
            "productize it with the sharp edges removed."
        ),
        when_applicable=(
            "Evidence shows repeated homegrown solutions to the same pain across "
            "unrelated teams or communities."
        ),
        failure_mode=(
            "Productizing one team's idiosyncratic workflow instead of the shared "
            "80% — the product fits its first user and nobody else."
        ),
    ),
    VenturePrinciple(
        key="composable-primitives",
        company="Notion",
        principle=(
            "Where users juggle five rigid single-purpose tools, offer fewer, more "
            "composable primitives that users assemble to fit their own workflow — "
            "flexibility becomes the moat."
        ),
        when_applicable=(
            "The pain is tool fragmentation and context-switching, not a missing "
            "capability."
        ),
        failure_mode=(
            "Infinite flexibility with no opinionated starting templates — the "
            "blank-canvas problem kills activation."
        ),
    ),
    VenturePrinciple(
        key="habit-loop-on-a-grind",
        company="Duolingo",
        principle=(
            "For pains that require sustained user effort over weeks, the product "
            "is the motivation system: streaks, progression, and immediate feedback "
            "make the grind self-reinforcing."
        ),
        when_applicable=(
            "Value only materializes if the user shows up repeatedly, and evidence "
            "shows people start but abandon existing solutions."
        ),
        failure_mode=(
            "Gamifying the metric instead of the outcome — engagement without "
            "progress, which users eventually notice and resent."
        ),
    ),
    VenturePrinciple(
        key="own-the-system-of-record",
        company="Shopify / Stripe (billing)",
        principle=(
            "Whoever durably holds the operational data (orders, subscriptions, "
            "runs, traces) becomes the platform others integrate with. Land as a "
            "tool, expand into the record of truth."
        ),
        when_applicable=(
            "The pain involves state scattered across tools with no single "
            "authoritative view — audits, billing, incident forensics."
        ),
        failure_mode=(
            "Claiming system-of-record status before earning daily-use trust with "
            "a wedge tool; nobody migrates their source of truth first."
        ),
    ),
    VenturePrinciple(
        key="sell-the-outcome-not-the-infra",
        company="Vercel / early AWS pattern",
        principle=(
            "When users assemble undifferentiated infrastructure to reach an "
            "outcome, sell the outcome with the infrastructure invisible — pay for "
            "deploys, not servers."
        ),
        when_applicable=(
            "Evidence shows sophisticated users doing repeated setup work that has "
            "no strategic value to them."
        ),
        failure_mode=(
            "Abstracting so hard that power users hit the ceiling and churn loudly "
            "— escape hatches are part of the product."
        ),
    ),
]


def principles_digest() -> str:
    """Compact rendering for inclusion in agent prompts."""
    lines = []
    for p in PRINCIPLES:
        lines.append(
            f"- [{p.key}] ({p.company}) {p.principle} APPLIES WHEN: {p.when_applicable} "
            f"FAILS WHEN: {p.failure_mode}"
        )
    return "\n".join(lines)
