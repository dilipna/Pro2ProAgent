# ADR-0002: Human-in-the-loop review via email, not the website

**Date:** 2026-07-05 · **Status:** Accepted (implementation in Phase 1)

## Context

The founder wants shortlist reviews delivered to their inbox; the public
website must not expose the review workflow. The pipeline pauses at the
review gate via LangGraph `interrupt()` + a persistent checkpointer.

## Decision

Outbound email with **signed one-click action links**. When a run reaches
the human gate, the service emails the reviewer a summary of shortlisted
problems with Approve / Reject links. Each link carries a signed,
single-use, expiring token; clicking it hits the API, which resumes the
paused graph with the decision.

Provider: an `EmailNotifier` port with two adapters — a real provider
(Resend or SMTP) and a console/log adapter for development, so the
pipeline runs without credentials.

## Trade-offs considered

- **Inbound email parsing** (reply "APPROVE"): requires an inbound mail
  webhook provider and parsing pipeline — meaningful infra for marginal UX
  gain. Rejected for now.
- **Honest caveat:** the action links are still HTTP endpoints on the API.
  "Not through the website" means the review UX lives in email and the
  endpoints are unlisted, token-gated, and no-indexed — not that HTTP is
  avoided entirely. This is the standard pattern (calendar invites,
  document approvals) and the right pragmatic reading of the requirement.

## Consequences

- Every review decision is persisted and doubles as labeled ground truth
  for the eval pipeline (Braintrust datasets) — see ADR-0003 (planned).
- Token signing/expiry becomes part of the API's security surface; tokens
  are single-use and scoped to one run.
