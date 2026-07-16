# ADR-0011: Research tool transport (in-process vs MCP) and run liveness

**Date:** 2026-07-15 · **Status:** Accepted

## Context

Every production discovery run — all of them, over several days — was stuck
at `research/stage_started` with zero LLM cost recorded, no error, and
`status="running"` forever. No ideas were ever produced, so no shortlist, no
review email, and the console approval queue was permanently empty ("no
awaiting decisions"). A run triggered live against prod reproduced it
exactly; the identical code ran end to end in ~20–70s locally.

The difference is the event loop, not the code. The Research Agent obtained
its tools from an **MCP server spawned as a stdio subprocess per tool call**
(`sys.executable -m p2pops.mcp.server`). On the local machine (Windows,
`ProactorEventLoop`) spawning that subprocess from inside the API's asyncio
task works. On the Render host (Linux, `SelectorEventLoop` — plain
`uvicorn`, so no `uvloop`), spawning it from inside the running server loop
hangs indefinitely. Nothing in that path had a timeout: not
`MultiServerMCPClient.get_tools()`, not the per-call session, not the chat
client, not the run itself. A single un-timed `await` that never returns is
what pinned every run at "running" — `execute_run`'s exception handler never
got the chance to mark it failed.

## Decisions

### 1. The in-server Research Agent calls its tools in-process; MCP stays as the default-tried transport with automatic fallback

The three tools (`search_hacker_news`, `search_web`, `read_article`) are
plain local Python functions. Spawning a subprocess per call to reach them
from inside the API event loop bought nothing but fragility. `research.py`
now defines the tools in-process with the **exact same contracts** the MCP
server exposes (same names — the system prompt references them by name —
same caps, same non-empty-return placeholders that keep Groq's
chat-completion schema happy). `config.research_tools` selects the transport:

- **`in_process`** (set in `render.yaml` for prod): bind the functions
  directly, no subprocess. Faster, and free of the Linux event-loop hang.
- **`mcp`** (code default): spawn the MCP stdio server — kept so the
  real-protocol tool-use showcase is exercised locally, in tests, and by any
  external MCP client (Claude Desktop etc.).

Either way research **auto-degrades to in-process** rather than failing: if
the MCP handshake times out (`mcp_startup_timeout_s`) or a per-call turn
raises/times out, a process-level circuit breaker trips and the run retries
in-process. A broken subprocess becomes a slower-but-working run, never a
stall. This is deliberately *not* removing MCP — `mcp/server.py` is
unchanged and remains the genuine protocol artifact; the internal hot path
just stops paying the subprocess tax.

### 2. No agent turn may run unbounded

`run_research` wraps each turn in `asyncio.wait_for(research_turn_timeout_s)`,
and the chat clients now carry `llm_request_timeout_s` (SDK default was 600s).
A wedged transport or connection now surfaces as a timeout the resilience
layer and `execute_run` can act on, so the failure is visible and the run
ends — instead of living forever.

### 3. In-flight runs are reconciled at startup

A run's background task cannot outlive the process that owns it, so a
redeploy or crash leaves its row stuck `running`/`building` with no error.
`repository.fail_orphaned_runs()`, called from the API lifespan on startup,
marks any such orphan `failed` (human-gate `awaiting_review` pauses are
checkpointed and genuinely resumable, so they are left alone). This both
cleared the historical backlog and makes every future restart self-healing.

## Consequences

- Prod discovery produces ideas again → shortlist → review email → the
  console approval queue populates. Verified locally end to end on the
  in-process path (which has no OS-specific subprocess behavior, so local
  success carries to the Linux host).
- The MCP server remains a real, tested, standalone artifact; the portfolio
  claim ("tool use over a real protocol") is intact and demonstrable by
  flipping `RESEARCH_TOOLS=mcp`.
- Follow-up worth considering: add `uvloop` in prod (robust subprocess
  support) if the MCP transport is ever wanted as the server default again.
