"""Promptfoo `exec:` provider — dispatches each test case to the REAL agent
code path (`analyst.analyze_idea`, `venture.agents.validate_problem`), not a
copy of the prompt. This is deliberate: a prompt-regression suite that tests
a duplicated prompt string only catches drift between the copy and the real
thing, never a real behavioral regression in the actual system.

Protocol (promptfoo's `exec:` provider, verified against its own source —
`ScriptCompletionProvider.callApi` in `providers/scriptCompletion.ts`):
argv[1] = rendered prompt (unused here — see below), argv[2] = provider
options JSON, argv[3] = call context JSON (`{"vars": {...}, ...}`). Exactly
one line of JSON on stdout becomes the provider's `output`.

`vars.agent` selects which real function runs; the rest of `vars` are its
inputs. promptfooconfig.yaml's `prompts:` entry is just a human-readable
scenario label — the actual "prompt" being tested is the one hardcoded in
the agent module the dispatch table below imports, so editing this file to
change what gets asserted never silently drifts from what production sends
the model.

DATA_DIR is pointed at a fresh temp directory before any p2pops import, so
each invocation gets an isolated ChromaDB dedupe store — CI runs must never
let one scenario's embedding accidentally "deduplicate" another's.
"""

import asyncio
import json
import os
import sys
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="p2pops-promptfoo-"))
# Telemetry is deliberately not configured for these one-shot subprocess
# invocations; suppress the (harmless) unconfigured-logfire warning so it
# doesn't pollute stderr in CI logs.
os.environ.setdefault("LOGFIRE_IGNORE_NO_CONFIG", "1")


async def _run_analyst(v: dict) -> dict:
    from p2pops.agents.analyst import analyze_idea
    from p2pops.models import DiscoveredIdea

    idea = DiscoveredIdea(
        title=v["title"], description=v["description"], source_url=v.get("source_url", "https://example.com")
    )
    result = await analyze_idea(idea)
    return result.model_dump()


async def _run_validator(v: dict) -> dict:
    from p2pops.venture.agents import _context, validate_problem
    from p2pops.venture.schemas import EvidenceBundle, EvidenceItem

    evidence = EvidenceBundle(
        query=v["title"],
        items=[EvidenceItem(**item) for item in v.get("evidence_items", [])],
    )
    ctx = _context(v["title"], v["description"], v.get("reasoning", ""), evidence)
    result = await validate_problem(ctx)
    return result.model_dump()


_DISPATCH = {
    "analyst": _run_analyst,
    "validator": _run_validator,
}


async def _main() -> None:
    # argv[1]=prompt (unused, see module docstring), argv[2]=options, argv[3]=context
    context = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    v = context.get("vars", {})
    agent = v.get("agent")
    handler = _DISPATCH.get(agent)
    if handler is None:
        raise ValueError(f"promptfoo test case missing/unknown vars.agent: {agent!r}")
    result = await handler(v)
    # Exactly one line: promptfoo trims stdout verbatim into `output`.
    print(json.dumps(result))


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
