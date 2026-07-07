import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getBuild, getOpportunity } from "@/lib/api";
import { Wordmark } from "@/components/nav";

// Operations view: metrics must be current, never a stale cached render.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Opportunity detail — ProToPro console",
  robots: { index: false },
};

interface Vision {
  product_name: string;
  one_liner: string;
  value_proposition: string;
  positioning: string;
  differentiation: string[];
  target_segment: string;
  execution_strategy: string;
  success_metrics: string[];
}

interface RankedDirection {
  name: string;
  composite: number;
}

interface Gate {
  gate: string;
  passed: boolean;
}

interface OpportunityDossier {
  idea_title: string;
  chosen_direction: string | null;
  ranking: RankedDirection[];
  gates: Gate[];
  vision: Vision | null;
}

interface ScaffoldFile {
  component: string;
  path: string;
  content: string;
}

interface BuildDossier {
  status: string;
  plan: { features: { name: string; description: string; priority: string }[] } | null;
  architecture: { components: { name: string; responsibility: string; tech: string }[] } | null;
  scaffold_files: ScaffoldFile[];
  qa_reports: { verdict: string; reasoning: string }[];
}

export default async function OpportunityDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const opp = await getOpportunity(id, { fresh: true });
  if (!opp) notFound();

  const dossier: OpportunityDossier | null = opp.dossier ? JSON.parse(opp.dossier) : null;
  const buildDetail = opp.build ? await getBuild(opp.build.id, { fresh: true }) : null;
  const buildDossier: BuildDossier | null = buildDetail?.dossier ? JSON.parse(buildDetail.dossier) : null;

  return (
    <div className="grain relative flex min-h-svh flex-col">
      <header className="border-b hairline">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <Link href="/" aria-label="Back to ProToPro">
              <Wordmark />
            </Link>
            <Link
              href="/console"
              className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist-600 transition-colors hover:text-mist-300"
            >
              / operations console / opportunity
            </Link>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-500">{opp.status}</span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-16">
        {dossier?.vision ? (
          <>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-maroon-300">
              {dossier.vision.target_segment}
            </p>
            <h1 className="mt-3 max-w-2xl text-balance text-4xl leading-tight tracking-[-0.01em]">
              {dossier.vision.product_name}
            </h1>
            <p className="mt-4 max-w-xl text-lg leading-relaxed text-mist-300">{dossier.vision.one_liner}</p>
            <p className="mt-2 max-w-xl text-sm text-mist-500">{dossier.vision.value_proposition}</p>

            <div className="mt-10 grid gap-5 sm:grid-cols-2">
              <div className="glass rounded-2xl p-6">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">Positioning</p>
                <p className="mt-2 text-sm text-mist-300">{dossier.vision.positioning}</p>
                <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                  Differentiation
                </p>
                <ul className="mt-2 list-disc pl-4 text-sm text-mist-300">
                  {dossier.vision.differentiation.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </div>
              <div className="glass rounded-2xl p-6">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                  Execution strategy
                </p>
                <p className="mt-2 text-sm text-mist-300">{dossier.vision.execution_strategy}</p>
                <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                  Success metrics
                </p>
                <ul className="mt-2 list-disc pl-4 text-sm text-mist-300">
                  {dossier.vision.success_metrics.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
            </div>
          </>
        ) : (
          <h1 className="text-3xl">{dossier?.idea_title ?? "Opportunity"}</h1>
        )}

        {dossier && dossier.ranking.length > 0 && (
          <section className="mt-14">
            <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">
              Direction ranking
            </p>
            <div className="space-y-2">
              {dossier.ranking.map((r) => (
                <div key={r.name} className="glass flex items-center justify-between rounded-xl px-5 py-3">
                  <span
                    className={`text-sm ${r.name === dossier.chosen_direction ? "text-mist-50" : "text-mist-400"}`}
                  >
                    {r.name}
                    {r.name === dossier.chosen_direction && " · chosen"}
                  </span>
                  <span className="font-mono text-sm text-mist-500">{r.composite}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {dossier && dossier.gates.length > 0 && (
          <section className="mt-10">
            <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">Gate history</p>
            <div className="flex flex-wrap gap-2">
              {dossier.gates.map((g, i) => (
                <span
                  key={i}
                  className={`rounded-full border hairline px-3 py-1 font-mono text-[10px] uppercase tracking-[0.1em] ${
                    g.passed ? "text-mist-500" : "text-maroon-300"
                  }`}
                >
                  {g.gate}: {g.passed ? "pass" : "fail"}
                </span>
              ))}
            </div>
          </section>
        )}

        <section className="mt-14 border-t hairline pt-10">
          <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">Build scaffold</p>
          {buildDossier ? (
            <div className="space-y-6">
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-500">
                Status: {buildDossier.status}
              </p>
              {buildDossier.plan && (
                <div className="glass rounded-2xl p-6">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">Plan</p>
                  <ul className="mt-2 space-y-1 text-sm text-mist-300">
                    {buildDossier.plan.features.map((f) => (
                      <li key={f.name}>
                        <span className="font-mono text-[10px] text-maroon-300">{f.priority}</span> {f.name} —{" "}
                        {f.description}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {buildDossier.architecture && (
                <div className="glass rounded-2xl p-6">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">Architecture</p>
                  <ul className="mt-2 space-y-1 text-sm text-mist-300">
                    {buildDossier.architecture.components.map((c) => (
                      <li key={c.name}>
                        {c.name} ({c.tech}) — {c.responsibility}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {buildDossier.scaffold_files.length > 0 && (
                <div className="space-y-3">
                  {buildDossier.scaffold_files.map((f) => (
                    <details key={f.component} className="glass rounded-2xl p-5">
                      <summary className="cursor-pointer font-mono text-[11px] uppercase tracking-[0.1em] text-mist-300">
                        {f.component} — {f.path}
                      </summary>
                      <pre className="mt-3 overflow-x-auto rounded-lg bg-[rgba(0,0,0,0.3)] p-4 text-xs text-mist-300">
                        {f.content}
                      </pre>
                    </details>
                  ))}
                </div>
              )}
              {buildDossier.qa_reports.length > 0 && (
                <div className="glass rounded-2xl p-6">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">QA</p>
                  {buildDossier.qa_reports.map((q, i) => (
                    <p key={i} className="mt-2 text-sm text-mist-300">
                      Round {i + 1}:{" "}
                      <span className="font-mono text-[10px] uppercase text-maroon-300">{q.verdict}</span> —{" "}
                      {q.reasoning}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="font-mono text-[11px] text-mist-600">
              Not yet scaffolded — run <code className="text-mist-400">p2pops-build {opp.id}</code>
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
