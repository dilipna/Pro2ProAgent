# ADR-0007: Containerization and deployment strategy

**Date:** 2026-07-07 · **Status:** Accepted

## Context

Through Phase 3, ProToPro ran only via `uv run p2pops-api` + `pnpm dev`, both
started manually, on one machine, with a CWD-relative data directory that had
already bitten a real bug (§12 of `PROJECT_BRAIN.md`: `data_dir="data"` created
a stray database when the API was started from the wrong directory). There was
no Docker, no CI, no deployment target — the single largest remaining gap
between "a well-engineered pipeline" and "an AI platform someone could
actually run." Phase A closes that gap.

## Decision

### Two images, one per tier, both multi-stage

- **`Dockerfile` (root, API).** `uv`-based builder stage resolves/installs into
  a self-contained venv (`--frozen --no-editable`, so the venv is portable
  independent of the source tree layout), then a plain `python:3.13-slim`
  runtime stage copies only that venv. `DATA_DIR=/app/data` is set explicitly
  in the image — the exact CWD-relative foot-gun above becomes structurally
  impossible in a container where the working directory is always `/app`.
- **`web/Dockerfile`.** Next.js 16 `output: "standalone"` (added to
  `next.config.ts` for this) traces the dependency graph and emits a
  self-contained `server.js`, so the runtime stage ships without the full
  `node_modules` tree. `PROTOPRO_API_URL` is read at container start, not
  baked in at build time — the same seeded-fallback contract from Phase 2
  (`web/src/lib/api.ts`) means the image builds and serves correctly even
  with zero knowledge of where the API will live.

Both images run as a non-root user and ship a `HEALTHCHECK` hitting a real
endpoint (`/api/v1/health` for the API, `/` for web) — not a bare "process is
running" check.

### A real health endpoint, not a stub

`GET /api/v1/health` (`api/app.py`) executes `SELECT 1` against the actual
database (`repository.ping()`) and returns 503 if it fails. This is the
target for Compose healthchecks, Kubernetes probes, and any future uptime
monitor — deliberately end-to-end (would have caught the `data_dir` bug
above at container-start time instead of on the first real query) rather
than a cheap "the process didn't crash" liveness stub.

### Docker Compose is the supported one-command path

`docker compose up --build` starts both services on a named volume
(`protopro-data`) that survives restarts. Host ports are overridable
(`API_PORT`/`WEB_PORT`) — found live during verification: this machine
already had unrelated containers bound to 8000. A `docker-compose.dev.yml`
override bind-mounts `src/` with `uvicorn --reload` for backend iteration;
web development deliberately stays native (`pnpm dev`) rather than
containerized, because a bind-mounted Next.js dev server inside Docker Desktop
on Windows/macOS cannot match native filesystem-watch performance, and there
is no compensating benefit (the web tier has no OS-level dependencies uv/pnpm
don't already provide locally).

### Kubernetes manifests exist to run the same images anywhere a cluster
already does — not because this project needs one

`deploy/k8s/` is a plain-manifest set (namespace, ConfigMap,
Secret template, API Deployment+PVC+Service, web Deployment+Service+HPA,
Ingress) behind one `kustomization.yaml`. Two decisions encode real
architecture facts rather than K8s boilerplate:

1. **API: `replicas: 1`, `strategy: Recreate`, one RWO PVC.** SQLite is
   single-writer; two API pods sharing one PVC would corrupt the database on
   concurrent writes. Horizontal API scaling is unlocked by the *already
   planned* Postgres migration (`database_url` is one connection string —
   see `PROJECT_BRAIN.md` §11), not by raising this number today.
2. **Web: `replicas: 2` + an HPA on CPU.** The web tier is stateless by
   construction (every page falls back to seeded content if the API is
   unreachable — Phase 2's whole design), so it is the tier that actually
   benefits from horizontal scaling, and it's where the HPA lives.

The manifests are honest about being a demonstration of container-orchestration
literacy, not a claim that this project's current traffic needs a cluster —
see the "no Kubernetes for the public demo" call below.

### Public demo target: Vercel (web) + a single container host (API) — not Kubernetes

For an always-on public demo, the pragmatic choice is Vercel for the Next.js
tier (first-party hosting, zero containers to manage) plus one small
container host (Fly.io/Railway/Render) for the API with a persistent volume.
Running a managed Kubernetes cluster for a single-operator portfolio demo
would be cost/complexity with no corresponding benefit — the same
"technology must earn its place" standard applied throughout this project
(see the OKF evaluation in `PROJECT_BRAIN.md` §12 for the precedent). The K8s
manifests remain the correct answer for "how would this run in an
organization that already operates a cluster," which is the question they
actually demonstrate competence at answering.

## Alternatives considered

- **Single combined image (API + web in one container).** Rejected: couples
  two independently-scalable tiers with different runtimes (Python vs.
  Node) and different failure/restart semantics into one deploy unit for no
  benefit.
- **`next start` instead of `output: "standalone"`.** Rejected: ships the
  full `node_modules` into the runtime image (slower pulls, larger attack
  surface) for no functional gain.
- **Managed Kubernetes as the only deployment story.** Rejected as the
  *primary* path (see above) but kept as a documented secondary path, since
  demonstrating it is itself part of the portfolio value.
- **Postgres now, to unlock multi-replica API immediately.** Rejected for
  this phase: no evidence current load needs it, and the migration is
  already a scoped, low-risk future step (connection-string change against
  an ORM-defined schema) — doing it opportunistically here would be scope
  creep on a containerization task.

## Consequences

- The `data_dir`-is-CWD-relative bug class is now structurally prevented
  inside containers (`DATA_DIR` always `/app/data`), though the underlying
  local-dev foot-gun (§12) is unchanged for anyone running `uv run p2pops-api`
  directly from the wrong directory.
- `engine.py`'s directory-creation logic had to change from re-parsing
  `database_url` (`rsplit("///", 1)`) to using `settings.data_dir` directly —
  a POSIX absolute `data_dir` (`/app/data`) produces a four-slash URL
  (`sqlite:////app/data/protopro.db`) where the old rsplit-based parsing
  silently produced a *relative* path, which crash-looped the API container
  on first boot (`PermissionError: 'app'`). Caught live during Compose
  verification, fixed, and re-verified — the same "root-cause live failures,
  don't guess" standard as ADR-0005's five bugs.
- Any new top-level-sounding directory under `src/` must still respect the
  anchored `.gitignore` rules from the `build/` incident noted in
  `PROJECT_BRAIN.md` §12 — `deploy/` was added and does not collide.
- Real deployment (the public URL) requires credentials Claude Code does not
  have (Vercel/Fly/Railway tokens, a GitHub remote to deploy from) — tracked
  as an explicit open item in the Session Handoff, not silently skipped.
