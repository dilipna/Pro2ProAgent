# P2POps — Problem to Product

A multi-agent AI operations platform: a small "company of agents" that discovers
real AI-related problems from communities like Hacker News and Reddit, filters
them through guardrails, puts a shortlist in front of a human every review cycle,
and — once approved — has its own PM, Architect, Engineer, and QA agents turn the
idea into a PRD and a runnable code scaffold.

The project exists to demonstrate a modern, production-shaped agent stack end to
end: orchestration, guardrails, RAG, tool use via MCP, observability, and evals.

## Stack

| Concern | Tool |
|---|---|
| Multi-agent orchestration | LangGraph (supervisor + subgraphs) |
| Tool exposure for agents | MCP (Model Context Protocol) |
| Memory / semantic dedupe | ChromaDB (RAG) |
| Guardrails | NeMo Guardrails |
| Model routing | LiteLLM (Anthropic direct or OpenRouter -- swap via one `.env` setting) |
| Tracing | LangSmith |
| App/pipeline telemetry | Pydantic Logfire |
| Offline agent evals | Braintrust |
| Prompt regression testing | Promptfoo (CI) |
| HITL dashboard / API | Streamlit + FastAPI |
| Article enrichment | Beautiful Soup |

## Status

- **Milestone 1 (bootstrap) — done.** Config, LiteLLM, LangSmith, and Logfire
  wired up behind a single traced call.
- **Milestone 2 (Research Agent) — done.** HN search + article-enrichment
  tools served over MCP; a LangGraph ReAct agent consumes them to surface
  candidate problems.
- **Milestone 3 (Supervisor + Analyst) — done.** A LangGraph Supervisor
  routes Research Agent output to the Analyst Agent, which runs each idea
  through a NeMo Guardrails input rail, checks it against a ChromaDB
  semantic-dedupe memory, scores it with a structured LLM call, and
  persists the result to SQLite.

The HITL review loop and the build squad (PM/Architect/Engineer/QA) land in
later milestones — see `implementation-notes.md` for the full plan and status.

## Setup

```bash
uv sync
cp .env.example .env
# set LLM_PROVIDER=anthropic or openrouter, and fill in the matching API key
uv run p2pops                       # bootstrap check: config + telemetry + one LLM call
uv run p2pops-research "some topic"  # Research Agent alone: searches HN, reasons over results
uv run p2pops-pipeline "some topic"  # full pipeline: Research -> Supervisor -> Analyst -> SQLite
uv run p2pops-mcp-server             # runs the MCP server standalone (stdio)
uv run pytest
```

`LANGSMITH_API_KEY` and `LOGFIRE_TOKEN` are optional — without them the app
still runs, it just won't ship traces anywhere. The Research Agent and
bootstrap check both need a funded key for whichever provider `LLM_PROVIDER`
selects; the HN search tool itself needs no keys at all.
