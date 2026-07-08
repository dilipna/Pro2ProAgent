import { API_BASE } from "@/lib/api";

/**
 * SSE passthrough: pipes the API's live run-event stream to the browser so
 * the console can watch a run in real time without the API's CORS surface
 * ever widening. The upstream body is streamed, not buffered.
 */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try {
    const upstream = await fetch(`${API_BASE}/api/v1/runs/${encodeURIComponent(id)}/stream`, {
      cache: "no-store",
    });
    if (!upstream.ok || !upstream.body) {
      return new Response("stream unavailable", { status: upstream.status || 502 });
    }
    return new Response(upstream.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch {
    return new Response("stream unavailable", { status: 502 });
  }
}
