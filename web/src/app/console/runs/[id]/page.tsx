import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRun } from "@/lib/api";
import { LiveTimeline } from "@/components/live-timeline";
import { Wordmark } from "@/components/nav";

// Operations view: metrics must be current, never a stale cached render.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Run detail — ProToPro console",
  robots: { index: false },
};

export default async function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const run = await getRun(id, { fresh: true });
  if (!run) notFound();

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
              / operations console / run
            </Link>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-500">{run.status}</span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-16">
        <h1 className="text-balance text-3xl leading-tight tracking-[-0.01em]">{run.topic}</h1>
        <p className="mt-2 font-mono text-[11px] text-mist-600">
          {run.id} · started {new Date(run.created_at).toLocaleString()}
          {run.completed_at && ` · completed ${new Date(run.completed_at).toLocaleString()}`}
          {run.source === "search" && run.keyword && ` · visitor search: “${run.keyword}”`}
        </p>
        {run.error && (
          <p className="mt-4 rounded-xl border hairline bg-[rgba(194,53,83,0.08)] p-4 text-sm text-maroon-300">
            {run.error}
          </p>
        )}

        <section className="mt-12">
          <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">Event timeline</p>
          {run.events.length === 0 ? (
            <p className="text-sm text-mist-600">No events recorded yet.</p>
          ) : (
            <ol className="space-y-4 border-l hairline pl-6">
              {run.events.map((e) => (
                <li key={e.id} className="relative">
                  <span className="absolute -left-[29px] top-1.5 h-2 w-2 rounded-full bg-maroon-400" />
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-maroon-300">{e.agent}</span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-mist-600">{e.event_type}</span>
                    {e.duration_ms != null && (
                      <span className="font-mono text-[10px] text-mist-600">{e.duration_ms.toFixed(0)}ms</span>
                    )}
                    <span className="font-mono text-[10px] text-mist-700">
                      {new Date(e.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-mist-300">{e.message}</p>
                </li>
              ))}
            </ol>
          )}
          {["running", "awaiting_review", "building"].includes(run.status) && (
            <LiveTimeline runId={run.id} skip={run.events.length} />
          )}
        </section>

        <section className="mt-14">
          <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">Ideas from this run</p>
          {run.ideas.length === 0 ? (
            <p className="text-sm text-mist-600">No ideas recorded for this run.</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {run.ideas.map((idea) => (
                <article key={idea.id} className="glass rounded-2xl p-5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mist-500">
                      {idea.status}
                    </span>
                    {idea.score != null && <span className="font-mono text-lg text-mist-50">{idea.score}</span>}
                  </div>
                  <h3 className="mt-2 text-sm leading-snug text-mist-100">{idea.title}</h3>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
