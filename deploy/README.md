# Deploying ProToPro

Three tiers of deployment, in increasing order of ceremony. All of them run
the same two images built by the root `Dockerfile` (API) and `web/Dockerfile`
(Next.js standalone).

## 1. Docker Compose (local / single host) — the supported path today

```bash
cp .env.example .env        # fill in at least a funded LLM provider key
docker compose up --build
# web → http://localhost:3000    api → http://localhost:8000
```

Data (SQLite, LangGraph checkpoints, Chroma) persists on the `protopro-data`
volume. The stack starts with **zero keys configured** — the site serves
seeded showcase content and the API serves reads — but starting a discovery
run needs a funded `LLM_PROVIDER` key, and real review emails need
`RESEND_API_KEY` + `REVIEW_EMAIL_TO`.

Backend hot-reload during development:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Web development stays native (`cd web && pnpm dev`) for fast refresh.

## 2. Kubernetes (`deploy/k8s/`)

Plain manifests behind one kustomization:

```bash
# 1. Create the secret (from your local .env; never commit secret.yaml)
kubectl apply -f deploy/k8s/namespace.yaml
kubectl -n protopro create secret generic protopro-secrets --from-env-file=.env

# 2. Everything else
kubectl apply -k deploy/k8s
```

Architecture facts the manifests encode (don't fight them):

- **API = 1 replica, `strategy: Recreate`, RWO PVC.** SQLite is
  single-writer; horizontal API scaling arrives with the planned Postgres
  migration (connection-string change), not by raising `replicas`.
- **Web = 2+ replicas + HPA.** Stateless by design: every page falls back to
  seeded content when the API is unreachable, so web pods are freely
  replaceable and CPU-scaled.
- **Probes hit `GET /api/v1/health`** (API) and `/` (web). Health answers
  503 when the database is unreachable, so readiness gates on real storage.
- Images are referenced as `protopro-*:local` for a local cluster
  (docker-desktop / kind / minikube with a loaded image). For a real cluster,
  point them at the registry CI pushes to and pin a tag.

## 3. Public demo (managed PaaS) — recommended target

For an always-on public demo the pragmatic split is:

- **Web → Vercel.** Next.js 16 first-party hosting; set `PROTOPRO_API_URL`
  to the API's public URL. Zero containers to manage.
- **API → a single small container host** (Fly.io / Railway / Render) running
  `protopro-api` with a persistent volume mounted at `/app/data` and the same
  env vars as `.env.example`. Set `APP_BASE_URL` to the public API URL so
  review-email links resolve, and set `API_TOKEN` — the mutating endpoints
  must not be open on a public host.

This is deliberately *not* Kubernetes: a portfolio demo with one operator
doesn't earn a managed cluster's cost/complexity. The manifests in
`deploy/k8s/` exist to run the same images anywhere a cluster already exists
(and to document the scaling story honestly).

Full rationale: `docs/adr/0007-containerization-and-deployment.md`.
