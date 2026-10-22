import { backendConnected, browserModeResponse } from "@/lib/backend-mode";
import { NextRequest } from "next/server";
import { API_BASE } from "@/lib/api";

async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  if (!backendConnected()) return browserModeResponse();
  const { path } = await params;
  const route = path.join("/");
  const allowed =
    /^(workspace\/config|briefs\/import|briefs\/[a-f0-9]{32}(?:\/(?:execute|execution))?|reviews\/[A-Za-z0-9_-]+|builds\/[a-f0-9]{32}\/(?:artifact|accept))$/.test(
      route,
    );
  if (!allowed)
    return Response.json(
      { detail: "Unknown workspace route" },
      { status: 404 },
    );
  const text = request.method === "POST" ? await request.text() : undefined;
  if (text && new TextEncoder().encode(text).length > 64000)
    return Response.json(
      { detail: "Keep the brief below 64 KB" },
      { status: 413 },
    );
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const auth = request.headers.get("authorization");
  if (auth) headers.Authorization = auth;
  try {
    const upstream = await fetch(`${API_BASE}/api/v1/${route}`, {
      method: request.method,
      headers,
      body: text,
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
    return Response.json(await upstream.json(), {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      {
        detail:
          "The operator API is unavailable. Your local brief is still available to export.",
      },
      { status: 502 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
