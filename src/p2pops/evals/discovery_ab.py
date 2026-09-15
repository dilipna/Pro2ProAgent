"""Discovery A/B: XploreMore-sourced vs HN/web-sourced research (ADR-0012).

Runs the real Research Agent and the real Analyst (guardrails -> dedupe ->
score) for each topic under two arms that differ only in discovery source:

- ``xploremore``: XPLOREMORE_API_URL set, so find_problems/get_problem are
  bound with the XploreMore prompt (HN/web tools still available).
- ``baseline``: XploreMore unset, so the pre-existing HN/web toolset and prompt.

Held equal across arms: model and provider, max_tokens, guardrails, analyst
prompt and shortlist threshold, the research step ceiling (both arms get the
XploreMore arm's larger ceiling), the turn timeout, per-call retry policy,
and a fresh token-per-minute window per trial (``--pause-s``). Arms alternate
order per topic. Each arm has its own fresh dedupe memory, and ideas are
remembered within the arm exactly as graph.analyst_node does, so the dedupe
rate means "new relative to this arm's earlier trials".

Nothing is written to the app database and no review email is sent.

    uv run p2pops-discovery-ab run --topics-file topics.txt --out ab.jsonl
    uv run p2pops-discovery-ab report --in ab.jsonl --out report.md

Not measured here, on purpose: human approval share and human quality ratings
need a human. The report says so instead of substituting a proxy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import random
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from p2pops import cost_tracking, memory, pricing
from p2pops.agents import analyst, research
from p2pops.chat_model import resolve_model
from p2pops.config import get_settings
from p2pops.tools import xploremore

ARMS = ("xploremore", "baseline")
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 7

logger = logging.getLogger(__name__)


class _RetryCounter(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.rate_limit_retries = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "hit a rate limit" in record.getMessage():
            self.rate_limit_retries += 1


class _Usage:
    def __init__(self) -> None:
        self.by_agent: dict[str, list[int]] = {}

    async def record(self, agent: str, tier: str, raw_message: object) -> None:
        usage = pricing.extract_usage(raw_message)
        if usage is None:
            return
        totals = self.by_agent.setdefault(agent.split(".")[0], [0, 0])
        totals[0] += usage.input_tokens
        totals[1] += usage.output_tokens


def _configure_arm(arm: str, data_root: Path, xploremore_url: str | None, xploremore_key: str | None) -> None:
    os.environ["XPLOREMORE_API_URL"] = (xploremore_url or "") if arm == "xploremore" else ""
    os.environ["XPLOREMORE_API_KEY"] = (xploremore_key or "") if arm == "xploremore" else ""
    os.environ["DATA_DIR"] = str(data_root / arm)
    os.environ["RESEARCH_TOOLS"] = "in_process"
    get_settings.cache_clear()
    memory._get_collection.cache_clear()
    # Trials are independent: no breaker state carries from one to the next.
    xploremore.reset()


async def run_trial(arm: str, topic: str) -> dict[str, Any]:
    usage = _Usage()
    retries = _RetryCounter()
    logging.getLogger("p2pops.resilience").addHandler(retries)
    captured: dict[str, Any] = {}
    original_turn = research._run_turn
    original_record = cost_tracking.record_usage

    async def capturing_turn(tools: list, t: str) -> dict:
        captured["tools"] = sorted(tool.name for tool in tools)
        result = await original_turn(tools, t)
        captured["messages"] = result.get("messages", [])
        return result

    research._run_turn = capturing_turn
    cost_tracking.record_usage = usage.record
    started = time.monotonic()
    trial: dict[str, Any] = {
        "arm": arm,
        "topic": topic,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": "/".join(resolve_model("default")),
        "xploremore_availability": xploremore.availability(),
    }
    try:
        try:
            report = await research.run_research(topic)
            trial["research_ok"] = True
        except Exception as exc:  # recorded, not hidden: failures are a result
            trial["research_ok"] = False
            trial["error"] = f"{type(exc).__name__}: {exc}"[:500]
            report = None
        trial["research_s"] = round(time.monotonic() - started, 1)
        messages = captured.get("messages", [])
        trial["tools_bound"] = captured.get("tools", [])
        trial["tool_calls"] = [
            call["name"] for m in messages if isinstance(m, AIMessage) for call in (m.tool_calls or [])
        ]
        ledger, unavailable = xploremore.observe_tool_messages(messages)
        trial["xploremore_problems_received"] = len(ledger)
        trial["xploremore_unavailable"] = unavailable

        ideas = []
        for idea in report.ideas if report else []:
            row: dict[str, Any] = {
                "title": idea.title,
                "source_url": idea.source_url,
                "problem_id": idea.problem_id,
                "voices": idea.provenance.voices if idea.provenance else None,
                "sources": idea.provenance.sources if idea.provenance else None,
            }
            try:
                analyzed = await analyst.analyze_idea(idea)
            except Exception as exc:
                row.update(status="analyst_error", error=f"{type(exc).__name__}: {exc}"[:300])
                ideas.append(row)
                continue
            row.update(
                status=analyzed.status,
                score=analyzed.score,
                guardrail_pass=analyzed.reasoning != "Blocked by guardrails",
            )
            if analyzed.status != "duplicate" and row["guardrail_pass"]:
                memory.remember(
                    uuid.uuid4().hex, f"{analyzed.title}\n{analyzed.description}", problem_id=analyzed.problem_id
                )
            ideas.append(row)
        trial["ideas"] = ideas
    finally:
        research._run_turn = original_turn
        cost_tracking.record_usage = original_record
        logging.getLogger("p2pops.resilience").removeHandler(retries)

    trial["total_s"] = round(time.monotonic() - started, 1)
    trial["tokens"] = {agent: {"input": t[0], "output": t[1]} for agent, t in usage.by_agent.items()}
    trial["rate_limit_retries"] = retries.rate_limit_retries
    return trial


async def run(args: argparse.Namespace) -> None:
    topics = [
        line.strip()
        for line in Path(args.topics_file).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    url = args.xploremore_url or os.environ.get("XPLOREMORE_API_URL")
    key = os.environ.get("XPLOREMORE_API_KEY")
    if not url:
        raise SystemExit("set XPLOREMORE_API_URL (or --xploremore-url) for the xploremore arm")
    data_root = Path(args.data_dir)
    # Same step ceiling for both arms, so the baseline is never cut short
    # where the XploreMore arm would not be.
    research.MAX_RESEARCH_STEPS = research.MAX_RESEARCH_STEPS_WITH_XPLOREMORE
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    first = True
    with out.open("a", encoding="utf-8", newline="\n") as sink:
        for index, topic in enumerate(topics):
            order = ARMS if index % 2 == 0 else tuple(reversed(ARMS))
            for arm in order:
                if not first:
                    await asyncio.sleep(args.pause_s)  # fresh TPM window for every trial
                first = False
                _configure_arm(arm, data_root, url, key)
                trial = await run_trial(arm, topic)
                trial["trial_index"] = index
                sink.write(json.dumps(trial, ensure_ascii=False) + "\n")
                sink.flush()
                shortlisted = sum(1 for i in trial["ideas"] if i.get("status") == "shortlisted")
                print(
                    f"[{arm:10}] {topic!r}: ok={trial['research_ok']} ideas={len(trial['ideas'])} "
                    f"shortlisted={shortlisted} tools={trial['tool_calls']} {trial['total_s']}s",
                    flush=True,
                )


# --- report ------------------------------------------------------------------------


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def cluster_bootstrap(trials: list[dict], numer, denom, seed: int = BOOTSTRAP_SEED) -> tuple[float, float, float]:
    """Ratio sum(numer)/sum(denom) with a 95% percentile CI, resampling whole
    trials: ideas from one research turn are not independent."""
    pairs = [(numer(t), denom(t)) for t in trials]
    total_d = sum(d for _, d in pairs)
    if not pairs or total_d == 0:
        return (math.nan, math.nan, math.nan)
    point = sum(n for n, _ in pairs) / total_d
    rng = random.Random(seed)
    stats = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        d = sum(x for _, x in sample)
        if d:
            stats.append(sum(x for x, _ in sample) / d)
    stats.sort()
    return (point, stats[int(0.025 * len(stats))], stats[int(0.975 * len(stats)) - 1])


def paired_difference(
    by_topic: dict[str, dict[str, dict]], metric, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float, float, int]:
    """Mean over topics of metric(xploremore) - metric(baseline), bootstrap over topics."""
    diffs = [
        metric(arms["xploremore"]) - metric(arms["baseline"])
        for arms in by_topic.values()
        if "xploremore" in arms and "baseline" in arms
    ]
    if not diffs:
        return (math.nan, math.nan, math.nan, 0)
    rng = random.Random(seed)
    means = sorted(
        sum(diffs[rng.randrange(len(diffs))] for _ in diffs) / len(diffs) for _ in range(BOOTSTRAP_ITERATIONS)
    )
    return (
        sum(diffs) / len(diffs),
        means[int(0.025 * len(means))],
        means[int(0.975 * len(means)) - 1],
        len(diffs),
    )


def _fmt(point: float, low: float, high: float, pct: bool = False, digits: int = 2) -> str:
    if math.isnan(point):
        return "n/a"
    if pct:
        return f"{100 * point:.0f}% [{100 * low:.0f}, {100 * high:.0f}]"
    return f"{point:.{digits}f} [{low:.{digits}f}, {high:.{digits}f}]"


def _tokens(trial: dict) -> int:
    return sum(v["input"] + v["output"] for v in trial.get("tokens", {}).values())


def _count(trial: dict, pred) -> int:
    return sum(1 for i in trial.get("ideas", []) if pred(i))


def build_report(trials: list[dict], source_name: str) -> str:
    lines: list[str] = []
    arms = {arm: [t for t in trials if t["arm"] == arm] for arm in ARMS}
    topics = sorted({t["topic"] for t in trials})
    n_min = min(len(v) for v in arms.values())

    lines.append("| Metric | XploreMore arm | Baseline (HN/web) arm |")
    lines.append("|---|---|---|")

    def row(name: str, fn) -> None:
        lines.append(f"| {name} | {fn(arms['xploremore'])} | {fn(arms['baseline'])} |")

    row("Trials", lambda ts: str(len(ts)))
    row(
        "Research turn completed (Wilson 95% CI)",
        lambda ts: _fmt(
            sum(t["research_ok"] for t in ts) / len(ts) if ts else math.nan,
            *wilson(sum(t["research_ok"] for t in ts), len(ts)),
            pct=True,
        ),
    )
    row("Ideas reported (total)", lambda ts: str(sum(len(t["ideas"]) for t in ts)))
    row("Ideas per trial", lambda ts: _fmt(*cluster_bootstrap(ts, lambda t: len(t["ideas"]), lambda t: 1)))
    row(
        "Guardrail pass rate",
        lambda ts: _fmt(
            *cluster_bootstrap(ts, lambda t: _count(t, lambda i: i.get("guardrail_pass")), lambda t: len(t["ideas"])),
            pct=True,
        ),
    )
    row(
        "Dedupe-new rate (of guardrail-passed)",
        lambda ts: _fmt(
            *cluster_bootstrap(
                ts,
                lambda t: _count(t, lambda i: i.get("guardrail_pass") and i.get("status") != "duplicate"),
                lambda t: _count(t, lambda i: i.get("guardrail_pass")),
            ),
            pct=True,
        ),
    )
    row(
        "Shortlisted share (of reported ideas)",
        lambda ts: _fmt(
            *cluster_bootstrap(
                ts, lambda t: _count(t, lambda i: i.get("status") == "shortlisted"), lambda t: len(t["ideas"])
            ),
            pct=True,
        ),
    )
    row("Shortlisted per trial", lambda ts: _fmt(
        *cluster_bootstrap(ts, lambda t: _count(t, lambda i: i.get("status") == "shortlisted"), lambda t: 1)
    ))
    row(
        "Analyst conviction, mean of scored ideas (0-100)",
        lambda ts: _fmt(
            *cluster_bootstrap(
                ts,
                lambda t: sum(i["score"] for i in t["ideas"] if i.get("score") is not None),
                lambda t: _count(t, lambda i: i.get("score") is not None),
            ),
            digits=1,
        ),
    )
    row(
        "Ideas carrying XploreMore provenance",
        lambda ts: _fmt(
            *cluster_bootstrap(ts, lambda t: _count(t, lambda i: i.get("problem_id") is not None), lambda t: len(t["ideas"])),
            pct=True,
        ),
    )
    row("Tokens per trial (research + analyst)", lambda ts: _fmt(
        *cluster_bootstrap(ts, _tokens, lambda t: 1), digits=0
    ))
    row(
        "Tokens per shortlisted idea",
        lambda ts: _fmt(
            *cluster_bootstrap(ts, _tokens, lambda t: _count(t, lambda i: i.get("status") == "shortlisted")), digits=0
        ),
    )
    row("Tool calls per trial", lambda ts: _fmt(*cluster_bootstrap(ts, lambda t: len(t["tool_calls"]), lambda t: 1)))
    row("Rate-limit retries (total)", lambda ts: str(sum(t.get("rate_limit_retries", 0) for t in ts)))
    row("Wall time per trial, s", lambda ts: _fmt(*cluster_bootstrap(ts, lambda t: t["total_s"], lambda t: 1), digits=0))
    row("Approval by a human", lambda ts: "not measured")
    row("Human rating of problem quality", lambda ts: "not measured")

    by_topic: dict[str, dict[str, dict]] = {}
    for t in trials:
        by_topic.setdefault(t["topic"], {})[t["arm"]] = t
    diff_rows = [
        ("Shortlisted per trial", lambda t: _count(t, lambda i: i.get("status") == "shortlisted"), 2),
        ("Ideas per trial", lambda t: len(t["ideas"]), 2),
        ("Tokens per trial", _tokens, 0),
    ]
    diffs = ["", "**Paired by topic (XploreMore minus baseline), bootstrap over topics:**", ""]
    diffs += ["| Metric | Mean difference [95% CI] | Topics |", "|---|---|---|"]
    for name, metric, digits in diff_rows:
        point, low, high, n = paired_difference(by_topic, metric)
        diffs.append(f"| {name} | {_fmt(point, low, high, digits=digits)} | {n} |")

    fallbacks = sum(1 for t in arms["xploremore"] if t.get("xploremore_unavailable"))
    header = [
        f"Source data: `{source_name}` ({len(trials)} trials, {len(topics)} topics, "
        f"{n_min} per arm minimum). Model: {', '.join(sorted({t['model'] for t in trials}))}.",
        "",
        f"XploreMore arm trials where XploreMore reported unavailable mid-run: {fallbacks}.",
        "",
    ]
    return "\n".join(header + lines + diffs) + "\n"


def report(args: argparse.Namespace) -> None:
    path = Path(args.input)
    trials = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    text = build_report(trials, path.name)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Discovery-source A/B for the Research Agent.")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--topics-file", required=True)
    run_p.add_argument("--out", required=True)
    run_p.add_argument("--data-dir", default="data/discovery_ab")
    run_p.add_argument("--xploremore-url", default=None)
    run_p.add_argument("--pause-s", type=float, default=65.0)
    rep_p = sub.add_parser("report")
    rep_p.add_argument("--in", dest="input", required=True)
    rep_p.add_argument("--out", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    if args.command == "run":
        os.environ.setdefault("LOGFIRE_IGNORE_NO_CONFIG", "1")
        os.environ["REVIEW_EMAIL_TO"] = ""
        os.environ["RESEND_API_KEY"] = ""
        asyncio.run(run(args))
    else:
        report(args)


if __name__ == "__main__":
    main()
