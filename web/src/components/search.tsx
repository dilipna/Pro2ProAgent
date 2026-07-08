"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { ApiIdea, ApiSearchResult } from "@/lib/api";

/**
 * Public keyword search: any visitor can point the discovery pipeline at a
 * topic. The run it starts flows through the exact same guardrails,
 * validation, and human approval gate as an autonomous run — searching
 * never skips the gate, and only the operator can green-light a build.
 */

const RUN_PHASE: Record<string, string> = {
  running: "Agents at work — discovering and validating candidates",
  awaiting_review: "Candidates shortlisted — awaiting human review",
  building: "Approved — venture pipeline and build squad running",
  completed: "Run complete — results are in the showcase and console",
  failed: "Run ended with an error — see the console for the timeline",
};

function ptpId(n: number | null): string | null {
  return n == null ? null : `PTP-${String(n).padStart(3, "0")}`;
}

function MatchRow({ idea }: { idea: ApiIdea }) {
  const id = ptpId(idea.ptp_number);
  const inner = (
    <span className="flex items-baseline justify-between gap-4">
      <span className="min-w-0">
        {id && (
          <span className="mr-3 font-mono text-[11px] tracking-[0.14em] text-maroon-300">{id}</span>
        )}
        <span className="text-sm text-mist-200">{idea.title}</span>
      </span>
      {idea.score != null && (
        <span className="shrink-0 font-mono text-[11px] text-mist-500">{idea.score} / 100</span>
      )}
    </span>
  );
  return (
    <li>
      {id ? (
        <Link
          href={`/showcase/${id.toLowerCase()}`}
          className="glass block rounded-xl px-4 py-3 transition-colors hover:border-maroon-700/50"
        >
          {inner}
        </Link>
      ) : (
        <span className="glass block rounded-xl px-4 py-3">{inner}</span>
      )}
    </li>
  );
}

export function Search() {
  const [keyword, setKeyword] = useState("");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ApiSearchResult | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const pollRun = useCallback(
    (runId: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`/api/search/runs/${runId}`);
          if (!res.ok) return;
          const run = (await res.json()) as { status: string };
          setRunStatus(run.status);
          // awaiting_review is a resting state (the human gate); stop there.
          if (["awaiting_review", "completed", "failed"].includes(run.status)) stopPolling();
        } catch {
          /* transient poll failure — keep trying until the interval clears */
        }
      }, 5000);
    },
    [stopPolling],
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = keyword.trim();
    if (trimmed.length < 3 || pending) return;
    setPending(true);
    setResult(null);
    setRunStatus(null);
    stopPolling();
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: trimmed }),
      });
      const body = (await res.json()) as ApiSearchResult;
      setResult(body);
      if (body.run_id && (body.outcome === "started" || body.outcome === "deduplicated")) {
        setRunStatus("running");
        pollRun(body.run_id);
      }
    } catch {
      setResult({
        outcome: "unavailable",
        message: "Something went wrong — please try again shortly.",
        run_id: null,
        matches: [],
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <section id="search" className="relative border-t hairline">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-maroon-300">
              Scoped discovery
            </p>
            <h2 className="mt-4 max-w-xl text-balance text-4xl leading-tight tracking-[-0.01em] md:text-5xl">
              Point the pipeline at a
              <span className="font-display italic text-maroon-300"> topic</span>
            </h2>
          </div>
          <p className="max-w-xs text-sm leading-relaxed text-mist-500">
            Type a keyword and the Research Agent runs a discovery pass scoped
            to it — same guardrails, same scoring, same human gate before
            anything gets built.
          </p>
        </div>

        <form onSubmit={submit} className="mt-10 flex max-w-2xl items-center gap-3">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            minLength={3}
            maxLength={80}
            required
            placeholder="e.g. prompt caching, agent evals, LLM cost tracking"
            aria-label="Search keyword"
            className="glass w-full rounded-full px-6 py-3 text-sm text-mist-100 placeholder:text-mist-600 focus:border-maroon-700/60 focus:outline-none"
          />
          <button
            type="submit"
            disabled={pending}
            className="ember-gloss shrink-0 rounded-full px-6 py-3 text-sm font-medium text-mist-50 shadow-ember-sm transition-shadow hover:shadow-ember disabled:opacity-60"
          >
            {pending ? "Searching…" : "Search"}
          </button>
        </form>

        {result && (
          <div className="mt-8 max-w-2xl">
            <p className="text-sm leading-relaxed text-mist-300">{result.message}</p>
            {runStatus && (
              <p className="mt-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-mist-500">
                {!["completed", "failed"].includes(runStatus) && (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-maroon-400" />
                )}
                {RUN_PHASE[runStatus] ?? runStatus}
              </p>
            )}
            {result.matches.length > 0 && (
              <div className="mt-6">
                <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.16em] text-mist-600">
                  Already validated in the showcase
                </p>
                <ul className="space-y-2">
                  {result.matches.map((idea) => (
                    <MatchRow key={idea.id} idea={idea} />
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
