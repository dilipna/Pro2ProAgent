import { API_BASE } from "@/lib/api";

/** Read-only run-status proxy for the search box's progress polling. */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try {
    const res = await fetch(`${API_BASE}/api/v1/runs/${encodeURIComponent(id)}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8_000),
    });
    if (!res.ok) return Response.json({ error: "not found" }, { status: res.status });
    const run = await res.json();
    return Response.json({ id: run.id, status: run.status, keyword: run.keyword });
  } catch {
    return Response.json({ error: "unreachable" }, { status: 502 });
  }
}
