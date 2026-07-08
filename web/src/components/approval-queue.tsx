"use client";

import { useCallback, useEffect, useState } from "react";
import type { ApiPendingReview } from "@/lib/api";

/**
 * In-console approval queue — the same human gate the email serves, without
 * depending on an inbox. Lists every pending review with its evidence and
 * one-click approve/reject. Decisions go through the operator-protected
 * JSON endpoint; the operator key is held in sessionStorage only, never
 * rendered into the page or stored server-side.
 */

const KEY_STORAGE = "protopro-operator-key";

type QueueState =
  | { phase: "loading" }
  | { phase: "unauthorized" }
  | { phase: "offline" }
  | { phase: "ready"; reviews: ApiPendingReview[] };

export function ApprovalQueue() {
  const [operatorKey, setOperatorKey] = useState("");
  const [state, setState] = useState<QueueState>({ phase: "loading" });
  const [deciding, setDeciding] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const fetchQueue = useCallback(async (key: string): Promise<QueueState> => {
    try {
      const res = await fetch("/api/console/reviews", {
        headers: key ? { Authorization: `Bearer ${key}` } : {},
        cache: "no-store",
      });
      if (res.status === 401) return { phase: "unauthorized" };
      if (!res.ok) return { phase: "offline" };
      return { phase: "ready", reviews: (await res.json()) as ApiPendingReview[] };
    } catch {
      return { phase: "offline" };
    }
  }, []);

  useEffect(() => {
    // Session key + first load resolve asynchronously; "loading" is already
    // the initial state, so nothing sets state synchronously in here.
    const key = sessionStorage.getItem(KEY_STORAGE) ?? "";
    let cancelled = false;
    void fetchQueue(key).then((next) => {
      if (cancelled) return;
      setOperatorKey(key);
      setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, [fetchQueue]);

  async function saveKey(e: React.FormEvent) {
    e.preventDefault();
    sessionStorage.setItem(KEY_STORAGE, operatorKey);
    setState({ phase: "loading" });
    setState(await fetchQueue(operatorKey));
  }

  async function decide(token: string, decision: "approve" | "reject") {
    setDeciding(token);
    setNotice(null);
    try {
      const res = await fetch(`/api/console/reviews/${token}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(operatorKey ? { Authorization: `Bearer ${operatorKey}` } : {}),
        },
        body: JSON.stringify({ decision }),
      });
      if (res.ok) {
        const body = (await res.json()) as { decision: string; run_resumed: boolean };
        setNotice(
          body.run_resumed
            ? `${body.decision} — all reviews are in, the pipeline resumes automatically.`
            : `${body.decision} — the run resumes once the remaining ideas are decided.`,
        );
      } else if (res.status === 401) {
        setNotice("Operator key rejected — check it and try again.");
      } else {
        setNotice("That review is no longer decidable (already used or expired).");
      }
    } catch {
      setNotice("Decision failed — the API is unreachable.");
    } finally {
      setDeciding(null);
      setState(await fetchQueue(operatorKey));
    }
  }

  const keyForm = (
    <form onSubmit={saveKey} className="flex items-center gap-2">
      <input
        type="password"
        value={operatorKey}
        onChange={(e) => setOperatorKey(e.target.value)}
        placeholder="operator key"
        aria-label="Operator key"
        className="glass w-44 rounded-full px-4 py-1.5 font-mono text-[11px] text-mist-200 placeholder:text-mist-600 focus:border-maroon-700/60 focus:outline-none"
      />
      <button
        type="submit"
        className="glass rounded-full px-4 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-400 transition-colors hover:text-maroon-300"
      >
        Unlock
      </button>
    </form>
  );

  return (
    <div className="mt-14">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">
          Pending approvals
        </p>
        {keyForm}
      </div>

      {notice && (
        <p className="mb-4 rounded-xl border hairline bg-[rgba(194,53,83,0.08)] px-4 py-3 text-sm text-mist-300">
          {notice}
        </p>
      )}

      {state.phase === "loading" && <p className="text-sm text-mist-600">Loading the queue…</p>}
      {state.phase === "offline" && (
        <p className="text-sm text-mist-600">API offline — the queue is unavailable.</p>
      )}
      {state.phase === "unauthorized" && (
        <p className="text-sm text-mist-600">
          Approvals need the operator key — enter it above. The email links keep working either
          way.
        </p>
      )}
      {state.phase === "ready" &&
        (state.reviews.length === 0 ? (
          <p className="text-sm text-mist-600">Nothing awaiting a decision.</p>
        ) : (
          <ul className="space-y-4">
            {state.reviews.map((review) => (
              <li key={review.token} className="glass rounded-2xl p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-3">
                      {review.idea.score != null && (
                        <span className="font-mono text-2xl text-mist-50">{review.idea.score}</span>
                      )}
                      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                        / 100 conviction
                      </span>
                    </div>
                    <h3 className="mt-2 text-lg leading-snug tracking-tight text-mist-100">
                      {review.idea.title}
                    </h3>
                    <p className="mt-2 max-w-2xl text-sm leading-relaxed text-mist-300">
                      {review.idea.description}
                    </p>
                    {review.idea.reasoning && (
                      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-mist-500">
                        {review.idea.reasoning}
                      </p>
                    )}
                    <a
                      href={review.idea.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 inline-block font-mono text-[10px] uppercase tracking-[0.12em] text-mist-500 transition-colors hover:text-maroon-300"
                    >
                      original source ↗
                    </a>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <button
                      onClick={() => decide(review.token, "approve")}
                      disabled={deciding === review.token}
                      className="ember-gloss rounded-full px-5 py-2.5 text-sm font-medium text-mist-50 shadow-ember-sm transition-shadow hover:shadow-ember disabled:opacity-60"
                    >
                      Approve build
                    </button>
                    <button
                      onClick={() => decide(review.token, "reject")}
                      disabled={deciding === review.token}
                      className="glass rounded-full px-5 py-2.5 text-sm text-mist-300 transition-colors hover:text-mist-50 disabled:opacity-60"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ))}
    </div>
  );
}
