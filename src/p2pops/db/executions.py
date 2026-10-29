"""Atomic admission and stable stage identities for imported-brief jobs."""

import json

from sqlalchemy import select, update

from ..briefs import digest, idea_snapshot
from ..execution_identity import execution_fingerprint
from .engine import session
from .models import Build, ExecutionJob, Idea, Opportunity, Review, Run, utcnow


async def enqueue(run_id: str) -> bool:
    async with session() as s:
        # Write first: SQLite owns its write lock while approval and admission
        # are checked. The claim and job identities commit together or not at all.
        claimed = await s.execute(
            update(Run)
            .where(Run.id == run_id, Run.source == "brief", Run.status == "ready_to_build")
            .values(status="building")
            .returning(Run.id)
        )
        if claimed.scalar_one_or_none() is None:
            return False
        ideas = list((await s.scalars(select(Idea).where(Idea.run_id == run_id))).all())
        if len(ideas) != 1 or ideas[0].status != "approved":
            return False  # session exit rolls back the uncommitted claim
        idea = ideas[0]
        review = await s.scalar(
            select(Review)
            .where(Review.idea_id == idea.id, Review.decision == "approved")
            .order_by(Review.decided_at.desc())
            .limit(1)
        )
        if review is None or not review.snapshot or not review.snapshot_sha256:
            return False
        if digest(json.loads(review.snapshot)) != review.snapshot_sha256:
            return False
        if digest(idea_snapshot(idea)) != review.snapshot_sha256:
            return False
        opportunity = Opportunity(run_id=run_id, idea_id=idea.id)
        s.add(opportunity)
        await s.flush()
        s.add(
            ExecutionJob(
                run_id=run_id,
                idea_id=idea.id,
                approval_sha256=review.snapshot_sha256,
                opportunity_id=opportunity.id,
                code_fingerprint=execution_fingerprint(),
            )
        )
        await s.commit()
        return True


async def get_job(run_id: str) -> ExecutionJob | None:
    async with session() as s:
        return await s.get(ExecutionJob, run_id)


async def pending_jobs() -> list[str]:
    async with session() as s:
        return list(
            (
                await s.scalars(
                    select(ExecutionJob.run_id)
                    .where(ExecutionJob.status.in_(("queued", "running")))
                    .order_by(ExecutionJob.created_at)
                )
            ).all()
        )


async def begin_attempt(run_id: str) -> None:
    async with session() as s:
        await s.execute(
            update(ExecutionJob)
            .where(ExecutionJob.run_id == run_id)
            .values(
                status="running",
                attempts=ExecutionJob.attempts + 1,
                updated_at=utcnow(),
                error=None,
            )
        )
        await s.commit()


async def ensure_build(run_id: str) -> str:
    """Called under the same-host job lock; row and pointer commit atomically."""
    async with session() as s:
        job = await s.get(ExecutionJob, run_id)
        if job is None:
            raise ValueError("execution job missing")
        if job.build_id:
            return job.build_id
        opportunity = await s.get(Opportunity, job.opportunity_id)
        if opportunity is None or opportunity.status != "complete" or not opportunity.dossier:
            raise ValueError("completed venture dossier required before build")
        build = Build(run_id=run_id, opportunity_id=job.opportunity_id)
        s.add(build)
        await s.flush()
        job.build_id = build.id
        job.stage = "build"
        job.updated_at = utcnow()
        await s.commit()
        return build.id


async def conclude(run_id: str, outcome: str, error: str | None = None) -> None:
    async with session() as s:
        job = await s.get(ExecutionJob, run_id)
        run = await s.get(Run, run_id)
        if job is None or run is None:
            raise ValueError("execution/run missing")
        job.status = "failed" if error else "complete"
        job.stage = "done"
        job.error = error
        job.updated_at = utcnow()
        run.status = outcome
        run.error = error
        run.completed_at = utcnow()
        await s.commit()
