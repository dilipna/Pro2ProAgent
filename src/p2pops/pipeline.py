"""CLI entrypoint for the full Research -> Analyst pipeline (Milestone 3)."""

import argparse
import asyncio

from .config import get_settings
from .graph import run_pipeline
from .telemetry import configure_telemetry


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the P2POps Research -> Analyst pipeline once.")
    parser.add_argument("topic", nargs="?", default="AI agent tooling", help="Topic to research")
    args = parser.parse_args()

    configure_telemetry()
    settings = get_settings()
    if not settings.active_api_key:
        print(f"No API key set for provider '{settings.llm_provider}' - add it to .env.")
        return

    result = asyncio.run(run_pipeline(args.topic))
    shortlist = result["shortlist"]

    if not shortlist:
        print("No ideas discovered for this topic.")
        return

    by_status: dict[str, int] = {}
    for idea in shortlist:
        by_status[idea.status] = by_status.get(idea.status, 0) + 1
    print(f"Processed {len(shortlist)} ideas: {by_status}")
    print()

    for idea in shortlist:
        if idea.status == "shortlisted":
            print(f"[{idea.status.upper()}] score={idea.score} - {idea.title}")
            print(f"  {idea.reasoning}")
            print(f"  {idea.source_url}\n")


if __name__ == "__main__":
    main()
