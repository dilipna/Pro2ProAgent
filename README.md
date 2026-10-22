# ProToPro — evidence into reviewed prototypes

**Inspect a reported problem, approve a bounded specification, and preserve the
source evidence through the build.**

[Open the workspace](https://protopro.vercel.app/workspace) ·
[Operations console](https://protopro.vercel.app/console) ·
[XploreMore](https://github.com/dilipna/xplore_more) ·
[Architecture and boundaries](docs/evidence-to-product.md) ·
[Recovery protocol](docs/durable-execution-protocol.md)

XploreMore classifies and clusters public problem reports. Pro2Pro accepts a
versioned problem brief with original sources, explicit scope and testable acceptance
criteria. A human reviews the exact snapshot before an explicitly started model build.
Generated artifacts need their own functional observations and acceptance decision.

The public workspace supports local brief inspection without accounts or inference.
Its bundled example is a labeled historical source record with a sample specification.
Operator import, approval and artifact decisions use the real API and database;
import and approval require no model. Model generation requires a configured provider
and remains unverified for this release. No paid calls, new generated products,
customer adoption or measured quality improvement are claimed.

## What works and what it proves

- Shared schema validation in both projects; idempotent imports and source-linked briefs.
- Operator authentication denies missing configuration. Missing/malformed guardrail
  decisions never authorize work and produce an operational error.
- Read-only email previews, deliberate confirmation, atomic single-use decisions,
  and a persisted SHA-256 binding approval to scope and evidence.
- Approved content is retained in venture/build prompts and dossiers. No model
  configuration leaves imported approved briefs ready, without a fabricated build.
- Candidate source inspection and a separate operator acceptance record tied to exact
  artifact bytes and observations for every approved criterion. Acceptance does not publish.
- Imported approved briefs use persisted execution jobs, stable stage identities and
  synchronous graph checkpoints. Real process-kill tests exercise recovery on the
  same persistent host; duplicate HTTP admission creates one job.
- The recorded discovery workbench transfers a validated edited draft into scope
  review within the same browser tab. JSON export/import works across deployments.
- Existing research, venture and browser-app generation paths remain available;
  deterministic tests exercise orchestration, not real-world model output quality.

## Run locally

Python 3.13, Node 24 and pnpm 10.28.2. The review journey needs no language model.

```bash
uv sync --all-groups --frozen
uv run ruff check src tests
uv run pytest -q
cd web
pnpm install --frozen-lockfile
pnpm test
pnpm lint
pnpm build
```

Follow [the local rehearsal](docs/evidence-to-product.md#local-rehearsal-without-paid-calls)
for API and web startup. Set `API_TOKEN` for operator access. Explicit development
bypass is off by default and cannot work outside development. Provider and publication
credentials are optional; do not add them just to inspect a brief.

Two existing memory tests exercise a small local ONNX embedding model; other offline
tests replace model calls with deterministic fakes. Live guardrail quality checks skip
without a configured provider key. Passing offline tests does not establish provider
availability or injection resistance.

## Architecture

```text
XploreMore /v1/problems + original source evidence
  -> versioned JSON brief -> local schema validation
  -> protected import -> exact snapshot review -> ready to build
  -> persisted execution job -> checkpointed venture -> checkpointed browser-app build
  -> functional observations -> separate artifact acceptance (no automatic publish)
```

[Existing integration ADR](docs/adr/0012-xploremore-problem-discovery.md) ·
[Brief contract](contracts/problem-brief.v1.schema.json) ·
[Failure-boundary tests](tests/test_brief_handoff.py) ·
[Real process recovery tests](tests/test_durable_execution.py) ·
[All 15 engineering ideas: fit and evidence](docs/engineering-idea-fit.md)

## Scope and limitations

Public reports are problem hypotheses, not customer validation. Machine-made labels
and clustering remain provisional. The stored 16-trial discovery comparison does not
establish that XploreMore yields better ideas. Imported approved-brief execution
can resume from persisted SQLite checkpoints on one host. Recovery requires the
same code/runtime fingerprint; changed approvals fail closed. Interrupted nodes
without a committed checkpoint can repeat, including provider requests. No
exactly-once billing or distributed-worker guarantee is claimed. Legacy discovery
execution retains its earlier orphan handling. Operator-submitted functional
observations are recorded assertions, not independent server verification.

Persistent storage is required; an ephemeral cloud disk does not establish recovery.
The existing Render API returned 503 during release intake, and its paid Starter
Blueprint was not applied. Source capabilities and local validation do not prove
remote availability. Publication and hosting changes require separate approval.

The older showcase includes historical outputs. A reachable HTML deployment does not
prove that its promised user workflow works. Use source-linked acceptance evidence
before describing a generated product as verified.

Historical session notes remain in PROJECT_BRAIN.md and implementation-notes.md;
current behavior and setup are described above and in docs/evidence-to-product.md.


## Inspect the recovery campaign

`tests/test_durable_execution.py` starts real child processes and terminates them
at five declared execution boundaries. Each scenario resumes against the same
isolated SQLite/checkpoint files. Tests also cover concurrent HTTP admission,
competing workers, approval/runtime changes, bounded graph failures, additive table
migration and an uninterrupted control. Model outputs are deterministic fixtures;
network access is forbidden inside the worker harness.

CI runs the suite with `--basetemp=test-evidence` and retains the five JSON recovery
receipts as an Actions artifact. Receipts include stable identities, checkpoint
counts, model-boundary sequences and artifact hashes. They do not establish actual
model quality, latency on production hardware or absence of provider double billing.
