import type { Metadata } from "next";
import Link from "next/link";
import { getCosts, getOpportunities, getRuns, getStats } from "@/lib/api";
import { Wordmark } from "@/components/nav";

// Operations view: metrics must be current, never a stale cached render.
export const dynamic = "force-dynamic";

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
      "Supervisor graph routing Research and Analyst; a second build-squad subgraph (PM/Architect/Engineer/QA) scaffolds completed opportunities on manual trigger.",
    stack: "LangGraph · MCP",
    status: "live",
  },
  {
    name: "Runs",
    detail:
      "Every pipeline execution as a first-class record: per-agent events and timing, queryable live via the API.",
    stack: "SQLite → Postgres",
    status: "live",
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
      "Shortlist review delivered by email; approve or reject resumes the paused graph automatically.",
    stack: "interrupt() · checkpointer",
    status: "live",
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
      "Analyst-vs-human agreement report from real review decisions, plus a live prompt regression suite exercising the actual agent code paths.",
    stack: "Promptfoo · homegrown eval",
    status: "live",
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

async function LiveMetrics() {
  const [stats, opportunities] = await Promise.all([
    getStats({ fresh: true }),
    getOpportunities({ fresh: true }),
  ]);
  const connected = stats !== null;
  const metrics = [
    { label: "discovery runs", value: stats ? String(stats.runs) : "—" },
    { label: "ideas analyzed", value: stats ? String(stats.ideas_total) : "—" },
    {
      label: "human-approved",
      value: stats ? String(stats.ideas_by_status["approved"] ?? 0) : "—",
    },
    {
      label: "opportunity dossiers",
      value: opportunities ? String(opportunities.length) : "—",
    },
  ];

  return (
    <div className="animate-rise glass mt-12 rounded-2xl p-6 [animation-delay:60ms]">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist-600">
          Live from the run store
        </p>
        {connected ? (
          <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-500">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-maroon-300" />
            API connected
          </span>
        ) : (
          <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
            <span className="h-1.5 w-1.5 rounded-full border border-mist-600" />
            API offline
          </span>
        )}
      </div>
      <div className="mt-6 grid grid-cols-2 gap-6 md:grid-cols-4">
        {metrics.map((m) => (
          <div key={m.label} className="flex flex-col gap-1.5">
            <span className="font-mono text-3xl tracking-tight text-mist-50">
              {m.value}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
              {m.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

async function RecentActivity() {
  const [runs, opportunities] = await Promise.all([
    getRuns({ fresh: true }),
    getOpportunities({ fresh: true }),
  ]);
  const recentRuns = (runs ?? []).slice(0, 8);
  const recentOpportunities = (opportunities ?? []).slice(0, 8);

  return (
    <div className="mt-14 grid gap-8 lg:grid-cols-2">
      <div>
        <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">Recent runs</p>
        {recentRuns.length === 0 ? (
          <p className="text-sm text-mist-600">No runs yet.</p>
        ) : (
          <ul className="space-y-2">
            {recentRuns.map((r) => (
              <li key={r.id}>
                <Link
                  href={`/console/runs/${r.id}`}
                  className="glass flex items-center justify-between rounded-xl px-4 py-3 text-sm transition-colors hover:border-maroon-700/50"
                >
                  <span className="truncate text-mist-200">{r.topic}</span>
                  <span className="ml-3 shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-mist-600">
                    {r.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">
          Recent opportunities
        </p>
        {recentOpportunities.length === 0 ? (
          <p className="text-sm text-mist-600">No opportunities yet.</p>
        ) : (
          <ul className="space-y-2">
            {recentOpportunities.map((o) => (
              <li key={o.id}>
                <Link
                  href={`/console/opportunities/${o.id}`}
                  className="glass flex items-center justify-between rounded-xl px-4 py-3 text-sm transition-colors hover:border-maroon-700/50"
                >
                  <span className="truncate font-mono text-[11px] text-mist-500">{o.id.slice(0, 8)}</span>
                  <span className="ml-3 shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-mist-600">
                    {o.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

async function CostPanel() {
  const costs = await getCosts({ fresh: true });

  return (
    <div className="mt-14">
      <div className="mb-4 flex items-baseline justify-between">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">LLM cost</p>
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-700">
          Estimated against list price · not a billing reconciliation
        </p>
      </div>

      {!costs || costs.calls === 0 ? (
        <div className="glass rounded-2xl p-6">
          <p className="text-sm text-mist-600">
            {costs ? "No LLM calls recorded yet." : "API offline — cost data unavailable."}
          </p>
        </div>
      ) : (
        <div className="glass rounded-2xl p-6">
          <div className="grid grid-cols-3 gap-6 border-b hairline pb-6 sm:grid-cols-4">
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-2xl tracking-tight text-mist-50">
                {formatCost(costs.estimated_cost_usd)}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                estimated spend
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-2xl tracking-tight text-mist-50">{costs.calls}</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                LLM calls
              </span>
            </div>
            <div className="hidden flex-col gap-1.5 sm:flex">
              <span className="font-mono text-2xl tracking-tight text-mist-50">
                {formatTokens(costs.input_tokens)}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                input tokens
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-2xl tracking-tight text-mist-50">
                {formatTokens(costs.output_tokens)}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                output tokens
              </span>
            </div>
          </div>

          <div className="mt-6 grid gap-8 sm:grid-cols-2">
            <div>
              <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">By agent</p>
              <ul className="space-y-2">
                {costs.by_agent
                  .slice()
                  .sort((a, b) => b.estimated_cost_usd - a.estimated_cost_usd)
                  .map((row) => (
                    <li key={row.agent} className="flex items-center justify-between text-sm">
                      <span className="truncate text-mist-300">{row.agent}</span>
                      <span className="ml-3 shrink-0 font-mono text-[11px] text-mist-500">
                        {formatCost(row.estimated_cost_usd)} · {row.calls} call{row.calls === 1 ? "" : "s"}
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
            <div>
              <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">By model</p>
              <ul className="space-y-2">
                {costs.by_model
                  .slice()
                  .sort((a, b) => b.estimated_cost_usd - a.estimated_cost_usd)
                  .map((row) => (
                    <li key={`${row.provider}/${row.model}`} className="flex items-center justify-between text-sm">
                      <span className="truncate text-mist-300">{row.model}</span>
                      <span className="ml-3 shrink-0 font-mono text-[11px] text-mist-500">
                        {formatCost(row.estimated_cost_usd)} · {formatTokens(row.tokens)} tok
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
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

        <LiveMetrics />

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

        <RecentActivity />

        <CostPanel />

        <p className="animate-rise mt-14 max-w-lg font-mono text-[11px] leading-relaxed text-mist-600 [animation-delay:480ms]">
          Metrics above are read live from the pipeline&apos;s run store.
          Click through a run or opportunity for its full event timeline or
          dossier.
        </p>
      </main>
    </div>
  );
}
