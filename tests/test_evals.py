from conftest import make_idea
from p2pops.db import repository as repo
from p2pops.evals.analyst_eval import evaluate


async def _decided_idea(run_id: str, *, score: int, decision: str) -> None:
    """Creates a shortlisted idea, a review for it, and records a human
    decision -- mirrors the real request_review -> record_decision path."""
    idea = await repo.save_idea(
        make_idea(status="shortlisted", title=f"idea-{score}", score=score), run_id=run_id
    )
    review = await repo.create_review(run_id, idea.id)
    await repo.record_decision(review.id, decision)


async def test_evaluate_empty(db):
    report = await evaluate()
    assert report.total_reviewed == 0
    assert report.agreement_rate is None
    assert report.mean_score_approved is None


async def test_evaluate_computes_agreement_and_score_means(db):
    run = await repo.create_run("t")
    await _decided_idea(run.id, score=90, decision="approved")
    await _decided_idea(run.id, score=80, decision="approved")
    await _decided_idea(run.id, score=40, decision="rejected")  # -> status "declined"

    report = await evaluate()

    assert report.total_reviewed == 3
    assert report.approved == 2
    assert report.declined == 1
    assert report.agreement_rate == 2 / 3
    assert report.mean_score_approved == 85.0
    assert report.mean_score_declined == 40.0
    assert len(report.rows) == 3


async def test_evaluate_reports_unreviewed_counts(db):
    run = await repo.create_run("t")
    await repo.save_idea(make_idea(status="shortlisted", title="pending review"), run_id=run.id)
    await repo.save_idea(make_idea(status="rejected", title="analyst rejected"), run_id=run.id)

    report = await evaluate()

    assert report.total_reviewed == 0
    assert report.still_shortlisted == 1
    assert report.analyst_rejected == 1
