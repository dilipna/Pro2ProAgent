"""First eval: does the Analyst's shortlist decision agree with the human reviewer?

Turns `Review.decision` records (surfaced on `Idea.status` as approved|declined,
see `db/repository.reviewed_ideas`) into a scored dataset -- the "human review
decisions become labeled datasets" step named in PROJECT_BRAIN.md/ADR discussions.

No BRAINTRUST_API_KEY exists for this account, so this ships as a dependency-free
local report rather than forcing an unavailable hosted tool (the same judgment
call already made for OKF: don't adopt a stack tool where it doesn't fit yet).
Structured so a Braintrust `Eval(...)` call could wrap `evaluate()`'s output
later without a rewrite, if a key is ever supplied.

Scope, stated honestly: every idea in `reviewed_ideas()` was already analyst-
shortlisted before a human ever saw it (only shortlisted ideas get review
tokens, see `graph.request_review_node`) -- so this measures the Analyst's
*precision* (of ideas it recommends, how many does the human actually want),
not recall. Recall would need a human to look at analyst-rejected ideas too,
which the pipeline never does today; that gap is reported, not hidden.
"""

import asyncio
from dataclasses import dataclass, field

from ..db import repository as repo
from ..db.engine import init_db
from ..db.models import Idea


@dataclass
class AnalystEvalReport:
    total_reviewed: int
    approved: int
    declined: int
    agreement_rate: float | None  # approved / total_reviewed
    mean_score_approved: float | None
    mean_score_declined: float | None
    still_shortlisted: int  # analyst-shortlisted, no human decision yet
    analyst_rejected: int  # never reached a human at all -- the recall gap
    rows: list[tuple[str, int | None, str]] = field(default_factory=list)  # (title, score, decision)

    def render(self) -> str:
        lines = [
            "Analyst shortlist vs. human decision",
            "=====================================",
            f"Reviewed (human decided): {self.total_reviewed}  "
            f"(approved {self.approved} / declined {self.declined})",
        ]
        if self.agreement_rate is not None:
            lines.append(f"Agreement rate (human approved | analyst shortlisted): {self.agreement_rate:.0%}")
        else:
            lines.append("Agreement rate: n/a -- no reviewed ideas yet")
        if self.mean_score_approved is not None:
            lines.append(f"Mean analyst score, human-approved:  {self.mean_score_approved:.1f}")
        if self.mean_score_declined is not None:
            lines.append(f"Mean analyst score, human-declined:  {self.mean_score_declined:.1f}")
        lines.append(f"Still awaiting a human decision: {self.still_shortlisted}")
        lines.append(
            f"Analyst-rejected (never shown to a human -- recall is unmeasured): {self.analyst_rejected}"
        )
        if self.total_reviewed < 20:
            lines.append(
                f"\nNote: N={self.total_reviewed} is small -- this is a scaffold for a real"
                " eval as the dataset grows, not a statistically significant benchmark."
            )
        lines.append("\nPer-idea:")
        for title, score, decision in self.rows:
            score_label = str(score) if score is not None else "-"
            lines.append(f"  [{decision:>8}] score={score_label:>3}  {title[:70]}")
        return "\n".join(lines)


def _mean(values: list[int]) -> float | None:
    return sum(values) / len(values) if values else None


async def evaluate() -> AnalystEvalReport:
    reviewed: list[Idea] = await repo.reviewed_ideas()
    counts = await repo.idea_counts()

    approved = [i for i in reviewed if i.status == "approved"]
    declined = [i for i in reviewed if i.status == "declined"]
    total = len(reviewed)

    return AnalystEvalReport(
        total_reviewed=total,
        approved=len(approved),
        declined=len(declined),
        agreement_rate=(len(approved) / total) if total else None,
        mean_score_approved=_mean([i.score for i in approved if i.score is not None]),
        mean_score_declined=_mean([i.score for i in declined if i.score is not None]),
        still_shortlisted=counts.get("shortlisted", 0),
        analyst_rejected=counts.get("rejected", 0),
        rows=[(i.title, i.score, i.status) for i in reviewed],
    )


async def _main() -> None:
    await init_db()
    report = await evaluate()
    print(report.render())


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
