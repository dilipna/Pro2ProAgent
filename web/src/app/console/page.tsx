import type { Metadata } from "next";
import Link from "next/link";
import { Wordmark } from "@/components/nav";

export const metadata: Metadata = {
  title: "Operations Console — ProToPro",
  description:
    "The engineering behind ProToPro: multi-agent orchestration, guardrails, evaluations, and observability.",
  robots: { index: false },
};

type ModuleStatus = "live" | "wiring";

const MODULES: {
  name: string;
  detail: string;
  stack: string;
  status: ModuleStatus;
}[] = [
  {
    name: "Orchestration",
    detail:
      "Supervisor graph routing the Research and Analyst agents; build-squad subgraph lands next.",
    stack: "LangGraph · MCP",
    status: "live",
  },
  {
    name: "Runs",
    detail:
      "Every pipeline execution as a first-class record: per-agent events, tokens, latency, cost.",
    stack: "SQLite → Postgres",
    status: "wiring",
  },
  {
    name: "Guardrails",
    detail:
      "Input rails filtering spam, noise, and off-topic content before anything reaches analysis.",
    stack: "NeMo Guardrails",
    status: "live",
  },
  {
    name: "Human gate",
    detail:
      "Shortlist review delivered by email; approve or reject resumes the paused graph.",
    stack: "interrupt() · checkpointer",
    status: "wiring",
  },
  {
    name: "Tracing",
    detail:
      "Full traces of every agent step and LLM call, plus app-level spans across the pipeline.",
    stack: "LangSmith · Logfire",
    status: "live",
  },
  {
    name: "Evaluations",
    detail:
      "Human review decisions become labeled datasets; prompt changes gate on regression suites.",
    stack: "Braintrust · Promptfoo",
    status: "wiring",
  },
];

function StatusDot({ status }: { status: ModuleStatus }) {
  if (status === "live") {
    return (
      <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-500">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-maroon-300" />
        Live
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
      <span className="h-1.5 w-1.5 rounded-full border border-mist-600" />
      Wiring
    </span>
  );
}

export default function ConsolePage() {
  return (
    <div className="grain relative flex min-h-svh flex-col">
      <header className="border-b hairline">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <Link href="/" aria-label="Back to ProToPro">
              <Wordmark />
            </Link>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist-600">
              / operations console
            </span>
          </div>
          <span className="rounded-full border hairline px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-500">
            Internal · read-only
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-16">
        <div className="animate-rise">
          <h1 className="max-w-2xl text-balance text-4xl leading-tight tracking-[-0.01em]">
            The engineering
            <span className="font-display italic text-maroon-300"> behind </span>
            the showcase
          </h1>
          <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-mist-300">
            ProToPro is not a website with a model behind it — it is an
            orchestrated system of agents with guardrails, evaluations, and
            full observability. This console exposes that machinery.
          </p>
        </div>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {MODULES.map((m, i) => (
            <article
              key={m.name}
              className="animate-rise glass flex h-full flex-col rounded-2xl p-6 transition-all duration-300 hover:border-maroon-700/50"
              style={{ animationDelay: `${90 + i * 60}ms` }}
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg tracking-tight">{m.name}</h2>
                <StatusDot status={m.status} />
              </div>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-mist-300">
                {m.detail}
              </p>
              <p className="mt-6 border-t hairline pt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                {m.stack}
              </p>
            </article>
          ))}
        </div>

        <p className="animate-rise mt-14 max-w-lg font-mono text-[11px] leading-relaxed text-mist-600 [animation-delay:480ms]">
          Deep views — run timelines, live graph state, per-agent cost, eval
          dashboards — connect here as the public API lands (Phase 1).
        </p>
      </main>
    </div>
  );
}
