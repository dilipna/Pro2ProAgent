from conftest import make_idea
from p2pops.db import repository as repo


async def test_run_lifecycle_and_events(db):
    run = await repo.create_run("agent observability")
    assert run.status == "running"

    await repo.add_event(run.id, "research", "stage_started", "topic: agent observability")
    await repo.add_event(run.id, "research", "stage_completed", "3 ideas", duration_ms=1200.5)
    await repo.set_run_status(run.id, "completed")

    events = await repo.events_after(run.id)
    assert [e.event_type for e in events] == ["stage_started", "stage_completed"]

    fetched = await repo.get_run(run.id)
    assert fetched.status == "completed"
    assert fetched.completed_at is not None
    assert await repo.run_count() == 1


async def test_ideas_and_counts(db):
    run = await repo.create_run("t")
    await repo.save_idea(make_idea("shortlisted"), run_id=run.id)
    await repo.save_idea(make_idea("rejected", title="Other"), run_id=run.id)

    assert len(await repo.list_ideas()) == 2
    assert len(await repo.list_ideas(status="shortlisted")) == 1
    assert await repo.idea_counts() == {"shortlisted": 1, "rejected": 1}


async def test_review_tokens_are_single_use(db):
    run = await repo.create_run("t")
    idea = await repo.save_idea(make_idea(), run_id=run.id)
    review = await repo.create_review(run.id, idea.id)

    assert len(await repo.pending_reviews(run.id)) == 1

    first = await repo.record_decision(review.id, "approved")
    assert first is not None
    second = await repo.record_decision(review.id, "rejected")
    assert second is None  # consumed

    ideas = await repo.list_ideas(status="approved")
    assert [i.id for i in ideas] == [idea.id]
    assert await repo.pending_reviews(run.id) == []
    assert await repo.decisions_for_run(run.id) == {idea.id: "approved"}


async def test_unknown_token_rejected(db):
    assert await repo.record_decision("not-a-real-token", "approved") is None


async def test_cost_summary_aggregates_across_agents_and_models(db):
    await repo.record_llm_call("venture/validator", "groq", "model-a", 100, 50, 0.01)
    await repo.record_llm_call("venture/validator", "groq", "model-a", 200, 100, 0.02)
    await repo.record_llm_call("analyst.scorer", "anthropic", "model-b", 30, 20, 0.05)

    summary = await repo.cost_summary()
    assert summary["calls"] == 3
    assert summary["input_tokens"] == 330
    assert summary["output_tokens"] == 170
    assert summary["estimated_cost_usd"] == 0.08

    by_agent = {row["agent"]: row for row in summary["by_agent"]}
    assert by_agent["venture/validator"]["calls"] == 2
    assert by_agent["venture/validator"]["tokens"] == 450
    assert by_agent["analyst.scorer"]["calls"] == 1

    by_model = {(row["provider"], row["model"]): row for row in summary["by_model"]}
    assert by_model[("groq", "model-a")]["calls"] == 2
    assert by_model[("anthropic", "model-b")]["calls"] == 1


async def test_cost_summary_empty_is_zeroed_not_null(db):
    summary = await repo.cost_summary()
    assert summary == {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "today_usd": 0.0,
        "daily_ceiling_usd": 1.0,
        "ceiling_exceeded": False,
        "by_agent": [],
        "by_model": [],
    }


async def test_cost_summary_today_feeds_ceiling_flag(db, monkeypatch):
    from p2pops.config import get_settings

    await repo.record_llm_call("venture/validator", "groq", "model-a", 100, 50, 0.75)
    summary = await repo.cost_summary()
    assert summary["today_usd"] == 0.75
    assert summary["ceiling_exceeded"] is False

    monkeypatch.setenv("DAILY_COST_CEILING_USD", "0.5")
    get_settings.cache_clear()
    try:
        summary = await repo.cost_summary()
        assert summary["daily_ceiling_usd"] == 0.5
        assert summary["ceiling_exceeded"] is True
    finally:
        get_settings.cache_clear()
