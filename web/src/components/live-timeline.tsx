"use client";

import { useEffect, useState } from "react";

/**
 * Live tail of a run's event timeline over SSE (proxied through
 * /api/console/runs/[id]/stream). Mounted under the server-rendered
 * timeline while a run is still moving; new events append in the same
 * visual style as they happen, so a run in progress is watchable in real
 * time rather than only after the fact.
 */

interface StreamedEvent {
  agent: string;
  message: string;
  duration_ms: number | null;
  at: string;
  event_type: string;
}

export function LiveTimeline({ runId, skip }: { runId: string; skip: number }) {
  const [events, setEvents] = useState<StreamedEvent[]>([]);
  const [finished, setFinished] = useState<string | null>(null);

  useEffect(() => {
    const source = new EventSource(`/api/console/runs/${runId}/stream`);
    let seen = 0;

    const onEvent = (e: MessageEvent, eventType: string) => {
      seen += 1;
      if (seen <= skip) return; // already server-rendered above
      try {
        const data = JSON.parse(e.data) as Omit<StreamedEvent, "event_type">;
        setEvents((prev) => [...prev, { ...data, event_type: eventType }]);
      } catch {
        /* malformed frame — skip it */
      }
    };

    // The API names its SSE events after RunEvent.event_type; listen to the
    // known set rather than only the default "message" channel.
    const types = [
      "stage_started",
      "stage_completed",
      "idea_discovered",
      "idea_analyzed",
      "review_requested",
      "review_decided",
      "gate_passed",
      "gate_failed",
      "error",
    ];
    for (const t of types) {
      source.addEventListener(t, (e) => onEvent(e as MessageEvent, t));
    }
    source.addEventListener("run_finished", (e) => {
      try {
        setFinished((JSON.parse((e as MessageEvent).data) as { status: string }).status);
      } catch {
        setFinished("finished");
      }
      source.close();
    });
    source.onerror = () => source.close();

    return () => source.close();
  }, [runId, skip]);

  if (events.length === 0 && !finished) {
    return (
      <p className="mt-4 flex items-center gap-2 pl-6 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-maroon-400" />
        streaming live — new events appear here as agents work
      </p>
    );
  }

  return (
    <>
      {events.length > 0 && (
        <ol className="mt-4 space-y-4 border-l hairline pl-6">
          {events.map((e, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[29px] top-1.5 h-2 w-2 animate-pulse rounded-full bg-maroon-300" />
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-maroon-300">
                  {e.agent}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-mist-600">
                  {e.event_type}
                </span>
                {e.duration_ms != null && (
                  <span className="font-mono text-[10px] text-mist-600">
                    {e.duration_ms.toFixed(0)}ms
                  </span>
                )}
                <span className="font-mono text-[10px] text-mist-700">
                  {new Date(e.at).toLocaleTimeString()}
                </span>
              </div>
              <p className="mt-1 text-sm leading-relaxed text-mist-300">{e.message}</p>
            </li>
          ))}
        </ol>
      )}
      {finished && (
        <p className="mt-4 pl-6 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
          run {finished}
        </p>
      )}
    </>
  );
}
