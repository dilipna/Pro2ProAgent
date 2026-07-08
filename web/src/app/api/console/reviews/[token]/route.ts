import { NextRequest } from "next/server";
import { API_BASE } from "@/lib/api";

/** Approve/reject one pending review from the console queue. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const auth = request.headers.get("authorization");
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "invalid request" }, { status: 400 });
  }
  try {
    const res = await fetch(`${API_BASE}/api/v1/reviews/${encodeURIComponent(token)}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(auth ? { Authorization: auth } : {}),
      },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    return Response.json(await res.json(), { status: res.status });
  } catch {
    return Response.json({ error: "API unreachable" }, { status: 502 });
  }
}
