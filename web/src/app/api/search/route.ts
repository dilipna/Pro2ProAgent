import { NextRequest } from "next/server";
import { API_BASE } from "@/lib/api";

/**
 * Server-side proxy for the public keyword search. The browser never talks
 * to the API host directly (keeps the API's CORS allowlist untouched), and
 * the caller's address is forwarded so per-client rate limiting works.
 */
export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "invalid request" }, { status: 400 });
  }

  const forwarded =
    request.headers.get("x-forwarded-for") ?? request.headers.get("x-real-ip") ?? "";

  try {
    const res = await fetch(`${API_BASE}/api/v1/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(forwarded ? { "X-Forwarded-For": forwarded } : {}),
      },
      body: JSON.stringify(body),
      cache: "no-store",
      // The search endpoint runs a guardrail LLM call before answering.
      signal: AbortSignal.timeout(30_000),
    });
    return Response.json(await res.json(), { status: res.status });
  } catch {
    return Response.json(
      { outcome: "unavailable", message: "The pipeline API is unreachable right now — try again shortly.", run_id: null, matches: [] },
      { status: 200 },
    );
  }
}
