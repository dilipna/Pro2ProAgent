# ADR-0003: CSS-only entrance animation for above-the-fold content

**Date:** 2026-07-05 · **Status:** Accepted

## Context

The first implementation animated hero content with a JS motion library
(`initial: opacity 0` → animate on mount / in-view). Headless-browser
verification during development showed the hero frozen at partial opacity —
and the underlying issue is real in production too: content whose
visibility depends on React hydration + JS animation hurts LCP, renders
blank/dim in crawlers and under failed or slow hydration, and is fragile
under IntersectionObserver quirks.

## Decision

- **Above the fold (hero, console header/cards):** CSS-only entrance
  (`animate-rise` keyframes with `animation-delay` staggers). Content is
  visible in server-rendered HTML immediately; animation is pure
  progressive enhancement and honors `prefers-reduced-motion`.
- **Below the fold:** the `Reveal` client component (motion library,
  `whileInView`, fires once) is appropriate — by definition the user
  scrolls to it after hydration.

## Consequences

- Hero and console render fully without JavaScript.
- Rule of thumb going forward: **nothing above the fold may depend on
  hydration to become visible.**
