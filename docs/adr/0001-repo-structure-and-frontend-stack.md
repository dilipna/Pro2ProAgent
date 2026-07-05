# ADR-0001: Modular monolith + Next.js frontend

**Date:** 2026-07-05 · **Status:** Accepted

## Context

ProToPro pivoted from a portfolio demo to a startup-grade product with a
premium public website, a recruiter-facing operations console, and an
email-driven HITL workflow. The original plan used Streamlit for the UI.

## Decision

1. **Reverse the Streamlit decision.** The web experience is a Next.js
   (App Router, TypeScript, Tailwind v4) app in `web/`, with a fully custom
   design system ("obsidian & ember": black stage, glossy maroon signal
   color, editorial serif display type). Streamlit's rerun model cannot
   deliver the required interaction design, motion, or brand identity.
2. **One Python service, one web app — a modular monolith.** The Python
   domain core, LangGraph orchestration, and (Phase 1) FastAPI API live in
   `src/p2pops`. Module boundaries (`api/`, `db/`, `agents/`, `graph`) are
   the future service seams; we do not split services before scale demands
   it.
3. **Brand vs. codename.** The product brand is **ProToPro**; the Python
   package keeps the internal codename `p2pops`. Renaming the package is
   pure churn with no user-visible value right now; revisit if the package
   is ever published.

## Consequences

- Two toolchains in one repo (uv/Python, pnpm/Node). Accepted: this is the
  industry-standard shape for an AI product with a real frontend.
- The web app talks to the Python service over a versioned REST/SSE API
  (Phase 1); until then, showcase content ships as typed seed data
  (`web/src/lib/cases.ts`) sourced from real pipeline output.
