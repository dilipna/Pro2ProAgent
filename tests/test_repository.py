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
