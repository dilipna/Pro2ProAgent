import Link from "next/link";
import { getShowcase, type ApiShowcaseItem } from "@/lib/api";
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

const STAGE_TO_STATUS: Record<ApiShowcaseItem["stage"], CaseStatus> = {
  validated: "validated",
  building: "building",
  live: "shipped",
};

const STAGE_ORDER: Record<ApiShowcaseItem["stage"], number> = {
  live: 0,
  building: 1,
  validated: 2,
};

function toCase(item: ApiShowcaseItem): CaseStudy {
  const id = `PTP-${String(item.ptp_number).padStart(3, "0")}`;
  return {
    id,
    title: item.title,
    insight: clamp(item.description),
    score: item.score ?? 0,
    source: sourceLabel(item.source_url),
    status: STAGE_TO_STATUS[item.stage],
    liveUrl: item.deploy_url,
    storyHref: `/showcase/${id.toLowerCase()}`,
  };
}

/**
 * Pipeline-numbered problems with their live lifecycle stage (shipped
 * first), topped up with the seeded cases so the grid always shows exactly
 * three cards — a partial row reads as broken, and the seeds are real
 * early pipeline output.
 */
async function loadCases(): Promise<CaseStudy[]> {
  const items = await getShowcase();
  const fromApi = [...(items ?? [])]
    .sort(
      (a, b) => STAGE_ORDER[a.stage] - STAGE_ORDER[b.stage] || b.ptp_number - a.ptp_number,
    )
    .slice(0, 3)
    .map(toCase);
  if (fromApi.length >= 3) return fromApi;
  return [...fromApi, ...CASES.filter((c) => !fromApi.some((f) => f.id === c.id))].slice(0, 3);
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
                  {c.storyHref ? (
                    <Link
                      href={c.storyHref}
                      className="transition-colors hover:text-maroon-200"
                    >
                      {c.title}
                    </Link>
                  ) : (
                    c.title
                  )}
                </h3>
                <p className="mt-4 flex-1 text-sm leading-relaxed text-mist-300">
                  {c.insight}
                </p>

                {c.liveUrl && (
                  <a
                    href={c.liveUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ember-gloss mt-6 self-start rounded-full px-5 py-2.5 text-sm font-medium text-mist-50 shadow-ember-sm transition-shadow hover:shadow-ember"
                  >
                    Visit the live product ↗
                  </a>
                )}

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
