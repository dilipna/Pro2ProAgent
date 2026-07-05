"""Milestone 1 bootstrap check: confirms telemetry and the LLM call path both work."""

from .config import get_settings
from .llm import complete
from .telemetry import configure_telemetry


def main() -> None:
    configure_telemetry()
    settings = get_settings()

    if not settings.active_api_key:
        print("P2POps bootstrap check")
        print("-" * 40)
        print(f"No API key set for provider '{settings.llm_provider}' - skipping the live LLM call.")
        print("Copy .env.example to .env and add your key, then re-run.")
        return

    reply = complete(
        "In one sentence, what is multi-agent orchestration?",
        agent="bootstrap-check",
    )
    print("P2POps bootstrap check")
    print("-" * 40)
    print(reply)


if __name__ == "__main__":
    main()
