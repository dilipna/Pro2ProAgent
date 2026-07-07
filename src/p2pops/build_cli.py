"""CLI entrypoint: scaffold one complete opportunity via the build-squad subgraph.

Manually triggered on purpose -- there is no automatic build-squad run
after a venture opportunity reaches `complete` (unlike venture pipeline,
which runs automatically right after human approval). The operator reads
the OpportunityDossier's product vision, then decides whether it's worth
spending another ~10-16 LLM calls to scaffold.
"""

import argparse
import asyncio

from .config import get_settings
from .db import repository as repo
from .db.engine import init_db
from .runner import execute_build, shutdown_pipeline
from .telemetry import configure_telemetry


async def _main(opportunity_id: str) -> None:
    await init_db()
    build = await execute_build(opportunity_id)
    print(f"build {build.id} for opportunity {opportunity_id} -> {build.status}\n")

    # Scope to this build's own slice of the timeline: run_id may belong
    # to an old, already-completed run with a long unrelated history.
    events = [
        e
        for e in await repo.events_after(build.run_id, after=build.created_at)
        if e.agent.startswith("build/")
    ]
    for event in events:
        duration = f" ({event.duration_ms:.0f} ms)" if event.duration_ms else ""
        print(f"  [{event.agent}] {event.event_type}: {event.message}{duration}")

    await shutdown_pipeline()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold one complete ProToPro opportunity.")
    parser.add_argument("opportunity_id", help="Opportunity id (must have status='complete')")
    args = parser.parse_args()

    configure_telemetry()
    settings = get_settings()
    if not settings.active_api_key:
        print(f"No API key set for provider '{settings.llm_provider}' - add it to .env.")
        return

    asyncio.run(_main(args.opportunity_id))


if __name__ == "__main__":
    main()
