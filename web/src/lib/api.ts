/**
 * Server-side client for the ProToPro API (`/api/v1`, FastAPI).
 *
 * Every helper resolves to `null` when the backend is unreachable, slow,
 * or returns a non-2xx — callers fall back to the seeded content in
 * `cases.ts`, so the public site renders fully even when the pipeline
 * host is down. The landing page must never look broken because the
 * backend is offline.
 *
 * Timeouts use Promise.race rather than an AbortSignal: Next.js opts a
 * fetch out of per-render memoization when a signal is passed, and the
 * hero ticker + showcase deliberately share one memoized /ideas request.
 */

const API_BASE = process.env.PROTOPRO_API_URL ?? "http://127.0.0.1:8000";

/** Landing-page data is ISR-cached; minutes of staleness are fine. */
const REVALIDATE_SECONDS = 120;

const TIMEOUT_MS = 2500;

export interface ApiIdea {
  id: string;
  run_id: string | null;
  title: string;
  description: string;
  source_url: string;
  score: number | null;
  reasoning: string | null;
  status: string;
  discovered_at: string;
}

export interface ApiOpportunity {
  id: string;
  run_id: string;
  idea_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface ApiStats {
  runs: number;
  ideas_by_status: Record<string, number>;
  ideas_total: number;
}

interface GetOptions {
  /** Bypass the data cache — for the console's always-current metrics. */
  fresh?: boolean;
}

function raceTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error(`API timed out after ${ms}ms`)), ms),
    ),
  ]);
}

async function get<T>(path: string, opts: GetOptions = {}): Promise<T | null> {
  try {
    const res = await raceTimeout(
      fetch(`${API_BASE}${path}`, {
        ...(opts.fresh
          ? { cache: "no-store" as const }
          : { next: { revalidate: REVALIDATE_SECONDS } }),
      }),
      TIMEOUT_MS,
    );
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function getIdeas(opts?: GetOptions): Promise<ApiIdea[] | null> {
  return get<ApiIdea[]>("/api/v1/ideas", opts);
}

export function getOpportunities(opts?: GetOptions): Promise<ApiOpportunity[] | null> {
  return get<ApiOpportunity[]>("/api/v1/opportunities", opts);
}

export function getStats(opts?: GetOptions): Promise<ApiStats | null> {
  return get<ApiStats>("/api/v1/stats", opts);
}
