import { Reveal } from "./reveal";

/**
 * Real numbers from live pipeline runs, inlined until the public API
 * (Phase 1) serves them from the run store.
 */
const STATS = [
  { value: "12", label: "problems analyzed" },
  { value: "10", label: "shortlisted by the analyst" },
  { value: "2", label: "guardrail-audited runs" },
  { value: "8", label: "agents on the roster" },
];

export function PipelineStats() {
  return (
    <section id="pipeline" className="relative border-t hairline">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <Reveal>
          <p className="mb-10 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">
            From the live pipeline
          </p>
        </Reveal>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border hairline bg-[rgba(246,241,242,0.06)] md:grid-cols-4">
          {STATS.map((s, i) => (
            <Reveal key={s.label} delay={i * 0.06} className="h-full">
              <div className="flex h-full flex-col gap-2 bg-ink-950 p-8">
                <span className="font-mono text-4xl tracking-tight text-mist-50">
                  {s.value}
                </span>
                <span className="text-[13px] leading-snug text-mist-500">
                  {s.label}
                </span>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
