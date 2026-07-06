"""CLI entrypoint: run the full pipeline once, recording a real Run.

Prints the event timeline as it lands. If the run pauses at the human
gate, the process exits cleanly — the checkpointed thread resumes later
via the review links (served by `p2pops-api`).
"""

import argparse
import asyncio

from .config import get_settings
from .db import repository as repo
from .db.engine import init_db
from .runner import execute_run, shutdown_pipeline
from .telemetry import configure_telemetry


async def _main(topic: str) -> None:
    await init_db()
    run = await repo.create_run(topic)
    print(f"run {run.id} started · topic: {topic}\n")

    await execute_run(run.id, topic)

    for event in await repo.events_after(run.id):
        duration = f" ({event.duration_ms:.0f} ms)" if event.duration_ms else ""
        print(f"  [{event.agent}] {event.event_type}: {event.message}{duration}")

    final = await repo.get_run(run.id)
    print(f"\nrun {run.id} -> {final.status}")
    if final.status == "awaiting_review":
        print("Shortlist sent to the human gate - check your email (or the log above")
        print("for console-adapter links). Approve/reject resumes the run via p2pops-api.")

    await shutdown_pipeline()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ProToPro pipeline once.")
    parser.add_argument("topic", nargs="?", default="AI agent tooling", help="Topic to research")
    args = parser.parse_args()

    configure_telemetry()
    settings = get_settings()
    if not settings.active_api_key:
        print(f"No API key set for provider '{settings.llm_provider}' - add it to .env.")
        return

    asyncio.run(_main(args.topic))


if __name__ == "__main__":
    main()
