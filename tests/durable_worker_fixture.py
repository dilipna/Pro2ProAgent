"""Child-process harness: real worker/graphs, deterministic model boundaries.

Not imported by production. Network requests fail rather than reaching a real
provider; kill barriers live only in this test harness.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from p2pops import durable
from p2pops.db import executions
from p2pops.db.engine import dispose_engine, init_db
from p2pops.venture import agents
from test_build import build_fake_structured as build_outputs
from test_venture import build_fake_structured as venture_outputs
from test_venture import fake_evidence

root = Path(os.environ["DATA_DIR"])
target = os.environ.get("PTP_TEST_PAUSE", "")
ledger = root / "fixture-calls.jsonl"


def record(label: str) -> None:
    with ledger.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"label": label}) + "\n")
        file.flush()


async def pause(label: str) -> None:
    if target == label:
        (root / "paused.json").write_text(json.dumps({"point": label, "pid": os.getpid()}))
        while True:
            await asyncio.sleep(0.1)


venture = venture_outputs(problem_is_real=True, stress_rounds_to_clean=1)
build = build_outputs(qa_rounds_to_clean=1)


async def structured(schema, prompt, **kwargs):
    family = "build" if ".build." in schema.__module__ else "venture"
    label = f"{family}:{schema.__name__}"
    record(label)
    await pause(label)
    return await (build if family == "build" else venture)(schema, prompt, **kwargs)


async def evidence(*args, **kwargs):
    record("venture:evidence")
    return await fake_evidence(*args, **kwargs)


async def completion(*args, **kwargs):
    record("build:file")
    return "// Deterministic restart fixture; no generated quality claim."


async def forbidden(*args, **kwargs):
    raise AssertionError("Live network is forbidden in the recovery campaign")


def forbidden_sync(*args, **kwargs):
    raise AssertionError("Live network is forbidden in the recovery campaign")


original_build = executions.ensure_build
original_conclude = executions.conclude


async def ensure_build(run_id):
    await pause("after_venture")
    return await original_build(run_id)


async def conclude(run_id, outcome, error=None):
    if error is None:
        await pause("before_complete")
    return await original_conclude(run_id, outcome, error)


async def main() -> None:
    httpx.AsyncClient.send = forbidden
    httpx.Client.send = forbidden_sync
    agents._structured = structured
    agents.gather_evidence = evidence
    agents._completion = completion
    executions.ensure_build = ensure_build
    executions.conclude = conclude
    await init_db()
    await pause("before_worker")
    try:
        result = await durable.process_job(sys.argv[1])
        print(json.dumps({"result": result}), flush=True)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
