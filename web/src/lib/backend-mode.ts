/** Server-only opt-in. A configured URL alone never enables upstream calls. */
export function backendConnected(): boolean {
  return process.env.PROTOPRO_BACKEND_MODE === "connected";
}
export function browserModeResponse(): Response {
  return Response.json(
    {
      mode: "browser",
      error: "Backend disabled in this browser edition.",
      detail:
        "Use the local setup for authenticated operator actions. Browser reviews and exports remain available.",
    },
    { status: 503, headers: { "Cache-Control": "no-store" } },
  );
}
