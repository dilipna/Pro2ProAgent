# Durable approved-brief execution: release protocol

Frozen before implementation, October 21, 2026, baseline `09cc932`.
Owner confirmed the previous session finished and transferred this release here.

## Bounded contract

Extend the existing imported-brief path from `ready_to_build` through venture,
build and `awaiting_acceptance`. Preserve the reviewed snapshot, operator gate,
generated artifact hash and withheld publication. Legacy discovery behavior is
outside the recovery guarantee. SQLite remains single-host/single-worker with
persistent local storage; ephemeral cloud disks do not establish durability.

Use existing LangGraph/SQLite checkpoints rather than a new workflow service.
Persist the job and its stable opportunity/build identifiers, atomically with
the execution claim. A same-host process lock prevents competing workers and
is released by process death. Resume checkpointed work using the same identities.
Completed durable outputs must not be recreated after a restart. An interrupted
node that never committed a checkpoint can repeat, including a provider request
or informational event. Do not claim exactly-once billing or all external effects.

The worker revalidates the original approved snapshot before resuming any graph.
Changed/rejected approval fails closed. No test invokes a real provider, sends
email, searches the web, or publishes a generated product. Credentials remain
absent; deterministic model fixtures test orchestration, not generation quality.

## Predeclared failure campaign and acceptance

1. Kill after execution is durably claimed but before a worker runs; a new process
   must discover that exact job instead of marking it irrecoverably failed.
2. Kill after a committed venture checkpoint and during a blocked later node;
   restart must preserve completed checkpoint output and original opportunity ID.
3. Kill between venture completion and build scheduling; retain the completed
   dossier and create only one build for this job.
4. Kill after a committed build checkpoint; resume to the same artifact/build ID,
   preserve the approved snapshot and end in awaiting_acceptance, never published.
5. Kill after final artifact persistence but before job completion; restarting
   must reuse the artifact rather than generate another build.
6. Competing same-host workers: one owns the job; the other reports busy/does
   not run model nodes. Release the lock by actual process termination and prove
   a fresh process can acquire it without a guessed timeout or stale-lock deletion.
7. Changed approval before recovery: no further node execution; explicit failed
   state and reason. Rejected/missing approval cannot enqueue a job.
8. Duplicate execute requests cannot create two persisted jobs or two builds.
   Exercise real HTTP/SQLite and concurrency, not only an exception assertion.
9. Missing model configuration leaves queued recovery inspectable and must not
   silently substitute a fixture as production output. Genuine nonretryable graph
   errors must be visible and bounded, not retried in an infinite startup loop.
10. Migration/restart preserves prior rows and legacy orphan handling. A valid
    uninterrupted control traverses the same production orchestration functions.

Use real child processes with isolated DATA_DIR and stable fixture responses.
Record source identity, kill point, exit codes, run/job/opportunity/build IDs,
checkpoint evidence, attempt/event counts, final artifact hash and excluded work.
Every attempted scenario is reported, including failures and unexpected repetitions.
Tests of transport/retry budgets remain separate from model-quality evaluation.

## Full release finish line

Fresh offline baseline, focused negative-to-positive cases, backend/web regression,
browser/mobile rehearsal, Docker and CI, accurate case study and recoverable release
artifacts. Preserve the existing evidence integration; do not modify XploreMore.
Independent functional artifact validation and budget reservation are separate
capabilities and must not be inferred from durable execution alone. Evaluate those
gaps after the recovery campaign, without claiming unimplemented fixes.

Production publication/deployment requires approval for a concrete tested release.
Hosting must remain zero-cost; do not apply the paid Render Starter Blueprint.
The existing API health returned 503 at intake. Verify deployment mapping and
state explicitly which local/recorded/remote paths actually work before closure.
