import { getIdeas } from "@/lib/api";
import { CASES, type CaseStatus, type CaseStudy } from "@/lib/cases";
import { Reveal } from "./reveal";

const STATUS_LABEL: Record<CaseStatus, string> = {
  validated: "Validated · build queue",
  building: "In build",
  shipped: "Shipped",
};

function sourceLabel(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return host.endsWith("ycombinator.com") || host.endsWith("algolia.com")
      ? "Hacker News"
      : host;
  } catch {
    return "discovery";
  }
}

function clamp(text: string, max = 240): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}

/**
 * Top pipeline-validated ideas (analyst-shortlisted or human-approved),
 * or the seeded cases when the API is down or has too few to fill the
 * grid — three cards or none, a partial row reads as broken.
 */
async function loadCases(): Promise<CaseStudy[]> {
  const ideas = await getIdeas();
  const validated = (ideas ?? []).filter(
    (idea) => idea.status === "approved" || idea.status === "shortlisted",
  );
  if (validated.length < 3) return CASES;
  return [...validated]
    .sort(
      (a, b) =>
        (b.score ?? 0) - (a.score ?? 0) ||
        Number(b.status === "approved") - Number(a.status === "approved"),
    )
    .slice(0, 3)
    .map((idea, i) => ({
      id: `PTP-${String(i + 1).padStart(3, "0")}`,
      title: idea.title,
      insight: clamp(idea.description),
      score: idea.score ?? 0,
      source: sourceLabel(idea.source_url),
      status: "validated" as const,
    }));
}

function ScoreMark({ score }: { score: number }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-mono text-3xl text-mist-50">{score}</span>
      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
        / 100 conviction
      </span>
    </div>
  );
}

export async function Showcase() {
  const cases = await loadCases();
  return (
    <section id="showcase" className="relative border-t hairline">
      <div className="mx-auto max-w-6xl px-6 py-28">
        <Reveal>
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-maroon-300">
                Showcase
              </p>
              <h2 className="mt-4 max-w-xl text-balance text-4xl leading-tight tracking-[-0.01em] md:text-5xl">
                Problems the pipeline has
                <span className="font-display italic text-maroon-300"> already </span>
                validated
              </h2>
            </div>
            <p className="max-w-xs text-sm leading-relaxed text-mist-500">
              Discovered in the wild, filtered by guardrails, scored by the
              Analyst. First builds are queued behind the human gate.
            </p>
          </div>
        </Reveal>

        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {cases.map((c, i) => (
            <Reveal key={c.id} delay={i * 0.08}>
              <article className="glass group relative flex h-full flex-col rounded-2xl p-7 transition-all duration-300 hover:border-maroon-700/50 hover:shadow-ember-sm">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] tracking-[0.14em] text-maroon-300">
                    {c.id}
                  </span>
                  <span className="rounded-full border hairline px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-mist-500">
                    {STATUS_LABEL[c.status]}
                  </span>
                </div>

                <h3 className="mt-6 text-pretty text-xl leading-snug tracking-tight">
                  {c.title}
                </h3>
                <p className="mt-4 flex-1 text-sm leading-relaxed text-mist-300">
                  {c.insight}
                </p>

                <div className="mt-8 flex items-end justify-between border-t hairline pt-6">
                  <ScoreMark score={c.score} />
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    via {c.source}
                  </span>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
