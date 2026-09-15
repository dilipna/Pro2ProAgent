"""Discovery A/B harness: statistics and report shape (no LLM calls)."""

import math

import pytest

from p2pops.evals import discovery_ab as ab


def _trial(arm, topic, statuses, scores, tokens=1000, ok=True, problem_ids=None):
    ideas = []
    for n, (status, score) in enumerate(zip(statuses, scores, strict=True)):
        ideas.append(
            {
                "status": status,
                "score": score,
                "guardrail_pass": status != "rejected_guardrail",
                "problem_id": (problem_ids or {}).get(n),
            }
        )
    return {
        "arm": arm,
        "topic": topic,
        "model": "groq/openai/gpt-oss-20b",
        "research_ok": ok,
        "ideas": ideas,
        "tool_calls": ["find_problems", "search_hacker_news"] if arm == "xploremore" else ["search_hacker_news"],
        "tokens": {"research": {"input": tokens, "output": 100}},
        "rate_limit_retries": 0,
        "total_s": 60.0,
        "xploremore_unavailable": [],
    }


def test_wilson_matches_known_values():
    low, high = ab.wilson(8, 10)
    assert low == pytest.approx(0.490, abs=0.001) and high == pytest.approx(0.943, abs=0.001)
    assert all(math.isnan(x) for x in ab.wilson(0, 0))


def test_cluster_bootstrap_point_is_the_pooled_ratio_and_ci_brackets_it():
    trials = [{"n": 1, "d": 2}, {"n": 3, "d": 4}, {"n": 0, "d": 3}]
    point, low, high = ab.cluster_bootstrap(trials, lambda t: t["n"], lambda t: t["d"])
    assert point == pytest.approx(4 / 9)
    assert low <= point <= high
    # Deterministic for a fixed seed.
    assert ab.cluster_bootstrap(trials, lambda t: t["n"], lambda t: t["d"]) == (point, low, high)


def test_paired_difference_uses_only_topics_with_both_arms():
    by_topic = {
        "a": {"xploremore": {"v": 3}, "baseline": {"v": 1}},
        "b": {"xploremore": {"v": 2}, "baseline": {"v": 2}},
        "c": {"xploremore": {"v": 9}},
    }
    point, low, high, n = ab.paired_difference(by_topic, lambda t: t["v"])
    assert n == 2 and point == 1.0 and low <= point <= high


def test_report_marks_human_metrics_not_measured_and_counts_correctly():
    trials = [
        _trial("xploremore", "t1", ["shortlisted", "rejected"], [70, 30], problem_ids={0: 5}),
        _trial("baseline", "t1", ["shortlisted", "duplicate"], [60, None]),
        _trial("xploremore", "t2", ["shortlisted"], [80], problem_ids={0: 6}),
        _trial("baseline", "t2", [], [], ok=False),
    ]
    text = ab.build_report(trials, "ab.jsonl")
    assert "| Approval by a human | not measured | not measured |" in text
    assert "| Trials | 2 | 2 |" in text
    assert "| Ideas reported (total) | 3 | 2 |" in text
    assert "| Ideas carrying XploreMore provenance | 67% [" in text
    assert "| Shortlisted share (of reported ideas) | 67% [" in text
    assert "| Topics |" in text
