"""Wires up LangSmith tracing and Logfire instrumentation for the whole app.

Call configure_telemetry() once, at process start, before any LLM or agent code runs.
"""

import logging
import os
import sys

import logfire

from .config import get_settings


def configure_telemetry() -> None:
    # LLM output (research reports, scoring reasoning) often contains
    # em-dashes and other non-ASCII characters that mangle on Windows'
    # default console codepage otherwise.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()

    if settings.langsmith_api_key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)

    logfire.configure(
        token=settings.logfire_token,
        service_name="p2pops",
        environment=settings.environment,
        send_to_logfire="if-token-present",
    )
    logfire.instrument_pydantic()
    logging.basicConfig(level=logging.INFO)
