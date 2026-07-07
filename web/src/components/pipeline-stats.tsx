import { getOpportunities, getStats } from "@/lib/api";
import { Reveal } from "./reveal";

/**
 * Numbers from real pipeline runs at the time they were seeded — shown
 * only when the live API is unreachable.
 */
const FALLBACK_STATS = [
  { value: "12", label: "problems analyzed" },
  { value: "10", label: "shortlisted by the analyst" },
  { value: "2", label: "guardrail-audited runs" },
  { value: "8", label: "agents on the roster" },
];

async function loadStats() {
  const [stats, opportunities] = await Promise.all([
    getStats(),
    getOpportunities(),
  ]);
  if (!stats || !opportunities) return FALLBACK_STATS;
  const byStatus = stats.ideas_by_status;
  // Everything that passed the analyst gate, whatever the human decided.
  const shortlisted =
    (byStatus["shortlisted"] ?? 0) +
    (byStatus["approved"] ?? 0) +
    (byStatus["declined"] ?? 0);
  return [
    { value: String(stats.ideas_total), label: "problems analyzed" },
    { value: String(shortlisted), label: "shortlisted by the analyst" },
    { value: String(stats.runs), label: "discovery runs" },
    { value: String(opportunities.length), label: "opportunity dossiers" },
  ];
}

export async function PipelineStats() {
  const stats = await loadStats();
  return (
    <section id="pipeline" className="relative border-t hairline">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <Reveal>
          <p className="mb-10 font-mono text-[11px] uppercase tracking-[0.18em] text-mist-600">
            From the live pipeline
          </p>
        </Reveal>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border hairline bg-[rgba(246,241,242,0.06)] md:grid-cols-4">
          {stats.map((s, i) => (
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
