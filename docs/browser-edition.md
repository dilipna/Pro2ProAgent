# Browser edition and local operation

The default website makes no upstream API calls. A configured API URL alone does
not enable the backend. The public experience consists of the recorded project
library, XploreMore brief validation and local scope review, JSON exports, and the
Decision Desk interactive reference.

Decision Desk uses fictional requests and browser localStorage. It never executes
tools or authorizes the authenticated pipeline. Notes are not encrypted: use only
non-sensitive demonstration content. Export before clearing browser site data.
This is a handcrafted reference, not an AI-generated product or model benchmark.

## Run the website without services

```sh
cd web
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open http://localhost:3000, then **Try a working prototype**. No environment file,
API token, provider key or hosting subscription is required. Internet is needed to
install dependencies and for Next.js build-time fonts; the demo itself uses local
assets. The demo HTML has a `connect-src 'none'` policy on Next.js hosting.

The six API proxy handlers reject requests with uncached 503 JSON in browser mode,
before reading credentials or sending upstream requests. The operator form and
console are replaced with local setup guidance. Recorded search filters bundled
records; it performs no fresh research or market validation.

## Run the full stack locally

```sh
docker compose up --build
```

Compose explicitly sets `PROTOPRO_BACKEND_MODE=connected` for the web service and
mounts the backend data volume. Its optional `.env` file can contain provider keys;
do not add keys merely to inspect or review briefs. For zero paid calls, leave
provider and publication credentials unset. Operator access requires `API_TOKEN`.
See [the local rehearsal](evidence-to-product.md#local-rehearsal-without-paid-calls).
Do not remove the data volume if you need its checkpoints and review history.

For a separately running backend and native Next.js server, set server-side env:

```sh
PROTOPRO_BACKEND_MODE=connected
PROTOPRO_API_URL=http://127.0.0.1:8000
```

Use the syntax appropriate for your shell or `web/.env.local`. Restart the server
after changing the mode. Do not enable connected mode on a public deployment unless
you intend to expose its public discovery endpoint and have reviewed provider costs.
Authenticated imports, exact-snapshot approval, durable execution and artifact
acceptance still belong to the backend; a local browser decision cannot replace them.
This release does not migrate existing remote data or create cloud resources.

## Maintain the public reference

Canonical files live in `examples/decision-desk`. Run:

```sh
node tools/sync-browser-demo.mjs
node tools/sync-browser-demo.mjs --check
```

The committed copy in `web/public/demos/decision-desk` allows a self-contained
`web/` Docker or Vercel build. Only its navigation back to the product is adapted.
The sync check normalizes checkout line endings and rejects source drift in CI.
The preview image is an actual reference screenshot, not a generated mockup.

The dedicated browser-edition reviewer exercises the real Next.js server, proxy
boundaries, local persistence, exports, responsive layout and discovery handoff.
The existing reference reviewer remains a separate test of the three-file source.
No browser check establishes complete accessibility, commercial value or generated
model quality.
