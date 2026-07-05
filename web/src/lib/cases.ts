/**
 * Showcase seed content.
 *
 * These are real problems discovered and scored by the ProToPro pipeline
 * (Research Agent -> Guardrails -> Analyst) in live runs — not invented
 * marketing copy. They are inlined here until the public API (Phase 1)
 * serves them from the pipeline database directly.
 */

export type CaseStatus = "validated" | "building" | "shipped";

export interface CaseStudy {
  id: string;
  title: string;
  insight: string;
  score: number;
  source: string;
  status: CaseStatus;
}

export const CASES: CaseStudy[] = [
  {
    id: "PTP-001",
    title: "Untracked token usage and surprise LLM bills in production agents",
    insight:
      "Teams running autonomous agents have no real-time view of per-query cost, no budget enforcement, and no alarm when an agent quietly burns 4.7x its expected token budget.",
    score: 87,
    source: "Hacker News",
    status: "validated",
  },
  {
    id: "PTP-002",
    title: "Multi-turn agent failures that single-turn evals never catch",
    insight:
      "Tool-argument mismatches, infinite loops, and false task completion only appear across turns — and the standard evaluation stack is built for single exchanges.",
    score: 85,
    source: "Community research",
    status: "validated",
  },
  {
    id: "PTP-003",
    title: "Code review has become the development pipeline bottleneck",
    insight:
      "Review backlogs now gate shipping velocity at scale, while reviewer attention is spent on style nits instead of the changes that can actually break production.",
    score: 78,
    source: "Hacker News",
    status: "validated",
  },
];

/** Rolling discovery feed — real idea titles surfaced by the Research Agent. */
export const DISCOVERY_FEED: string[] = [
  "Agent hijacking has no standard evaluation framework",
  "Eval results do not transfer between agent frameworks",
  "Benchmarking 9 models cost $40,000 and three weeks",
  "Production monitors see HTTP 200 while agents leak PII",
  "No cause-and-effect context when an agent fails mid-run",
  "Per-query agent costs are invisible until the invoice",
  "Audit trails fragment across multi-framework deployments",
  "Metrics look green while the user experience degrades",
  "AI-generated code arrives in review with zero context",
  "Stylistic nits crowd out substantive code review",
];
