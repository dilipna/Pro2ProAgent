import { NextRequest } from "next/server";
import { API_BASE } from "@/lib/api";

/**
 * Approval-queue proxy. The operator key is supplied by the console UI per
 * request and passed through verbatim — the web tier stores no secret.
 */
export async function GET(request: NextRequest) {
  const auth = request.headers.get("authorization");
  try {
    const res = await fetch(`${API_BASE}/api/v1/reviews/pending`, {
      headers: auth ? { Authorization: auth } : {},
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return Response.json(await res.json(), { status: res.status });
  } catch {
    return Response.json({ error: "API unreachable" }, { status: 502 });
  }
}
