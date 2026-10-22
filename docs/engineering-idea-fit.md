# Applying the 15 engineering ideas to ProToPro

Reviewed against the full supplied Build/Why descriptions, October 21, 2026.
These are capability decisions, not claims that all 15 are implemented.
The objective is a coherent evidence-to-product system with demonstrable boundaries.

| Idea | Fit and decision | Current evidence / remaining work |
| --- | --- | --- |
| 1. Dynamic context assembler | Strong fit for growing evidence and generated files; evaluate next. | The brief has size/scope bounds, but these are not per-model token budgets. Preserve immutable approved scope when assembling context. |
| 2. Durable state machine | Core addition in this release. | Persistent execution admission, stable IDs, SQLite graph checkpoints and same-host process exclusion. Real kill/restart campaign; no exactly-once provider-billing claim. Existing operator approval instead of adding Slack. |
| 3. Raw MCP server/client | Preserve existing MCP integration. | Do not replace working SDK tools merely to claim a raw implementation. Protocol/access tests are more valuable than duplicate plumbing. |
| 4. Triage router | Conditional future fit. | No measured workload or model-quality comparison establishes a 95/5 split. Avoid invented routing savings. |
| 5. Self-correcting RAG | Better addressed at evidence retrieval boundaries. | Existing venture evidence review is not automatically self-correcting RAG. Source sufficiency and abstention deserve measured evaluation before this label. |
| 6. Three-tier memory | Defer new memory tiers. | Existing memory must remain bounded and independently testable; durable job state is not semantic/episodic memory. |
| 7. Trajectory CI gate | Strong fit for approved build orchestration. | Recovery campaign records model-boundary sequences and protects completed stages. The uninterrupted control asserts causal stage ordering; CI retains kill-scenario receipts. This is a bounded workflow gate, not a general golden-DAG evaluator. |
| 8. Sanitization proxy | Strong trust-boundary fit. | Strict schemas and exact snapshot approval exist. These do not prove prompt-injection resistance; scoped tools and adversarial tests need separate evidence. |
| 9. Voice interruption | Exclude from this product. | Evidence inspection and scope review benefit from a visual, deliberate interface. Voice would add latency and hosting complexity without solving this workflow. |
| 10. DPO feedback | Defer. | No legitimate, representative preference dataset or validated training/evaluation split exists. Do not turn operator approval into a model training claim. |
| 11. Cost kill-switch | Strong fit; evaluate after recovery. | Existing estimated spend admission is not an atomic per-call reservation. Unknown prices must not be presented as free calls. No live paid evaluation is authorized. |
| 12. Shadow comparator | Offline comparison is the appropriate initial form. | No traffic mirroring or extra model spending. Recorded comparisons must distinguish orchestration fixtures from model quality. |
| 13. Computer-use fallback | Exclude from autonomous external actions here. | Browser-based artifact validation is a distinct useful capability; it must not silently bypass a failing external API or human approval. |
| 14. PII proxy | Conditional future fit. | Current public-source brief workflow does not establish private-data readiness. Do not claim complete PII protection based on a regex redactor. |
| 15. Architecture teardown | Core release documentation. | Publish source-linked architecture, crash campaign, limitations and observed hosting state after release approval. No fabricated production scale, cost savings or benchmark results. |

## Integration boundary

The recorded XploreMore workbench inside ProToPro now offers a same-origin,
tab-scoped draft handoff into scope review. It carries validated evidence and
edited specification only. It does not carry approval or credentials. JSON export
and import remain the interoperable path from the separate XploreMore deployment.
No producer-side XploreMore source has been modified by this release.

## Release priorities

1. Finish bounded recovery and migration regressions with inspectable receipts.
2. Validate the whole discovery, scope, local rehearsal and operator journey.
3. Evaluate independent artifact behavior checks and explicit model-call budgets.
4. Complete a responsive, accessible website and reproducible architecture evidence.
5. Prepare an exact release, then obtain source publication and deployment approval.
