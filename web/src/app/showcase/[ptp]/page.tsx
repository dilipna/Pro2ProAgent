import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getShowcaseItem, type ApiShowcaseDetail } from "@/lib/api";
import { SEED_STORIES } from "@/lib/seed-story";
import { Wordmark } from "@/components/nav";

/**
 * The permanent problem-to-product story for one PTP item: the original
 * problem and evidence, the Analyst's verdict, the human decision, the
 * venture pipeline's product vision, the build squad's work (with QA
 * rounds), the full event-timeline replay, and — once shipped — the live
 * product link. Every published product is a durable case study, not just
 * a showcase card with an outbound link.
 */

export const revalidate = 60;

export const metadata: Metadata = {
  title: "Problem-to-product story — ProToPro",
};

const STAGE_LABEL: Record<ApiShowcaseDetail["stage"], string> = {
  validated: "Validated · build queue",
  building: "In build",
  live: "Live",
};

/* --- Dossier shapes (parsed subsets of the backend's pydantic schemas) --- */

interface VentureDossier {
  status?: string;
  chosen_direction?: string | null;
  validation?: { evidence_summary?: string; confidence?: number } | null;
  vision?: {
    product_name?: string;
    one_liner?: string;
    value_proposition?: string;
    positioning?: string;
    differentiation?: string[];
    target_segment?: string;
    execution_strategy?: string;
    success_metrics?: string[];
    known_risks?: string[];
  } | null;
  gates?: { gate: string; passed: boolean; reasons: string[] }[];
}

interface BuildDossier {
  status?: string;
  product_name?: string | null;
  plan?: {
    features?: { name: string; priority: string; description: string }[];
    tech_stack?: { layer: string; choice: string; rationale: string }[];
    non_goals?: string[];
  } | null;
  architecture?: {
    components?: { name: string; responsibility: string; tech: string }[];
  } | null;
  scaffold_files?: { component: string; path: string; language: string }[];
  qa_reports?: { verdict: string; reasoning: string; issues: unknown[] }[];
  gates?: { gate: string; passed: boolean; reasons: string[] }[];
  deploy_url?: string | null;
}

function parse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.18em] text-maroon-300">
      {children}
    </p>
  );
}

async function loadStory(ptpNumber: number): Promise<ApiShowcaseDetail | null> {
  const fromApi = await getShowcaseItem(ptpNumber);
  return fromApi ?? SEED_STORIES[ptpNumber] ?? null;
}

export default async function StoryPage({ params }: { params: Promise<{ ptp: string }> }) {
  const { ptp } = await params;
  const match = /^ptp-(\d{3,})$/i.exec(ptp);
  if (!match) notFound();
  const ptpNumber = Number(match[1]);
  const story = await loadStory(ptpNumber);
  if (!story) notFound();

  const id = `PTP-${String(story.ptp_number).padStart(3, "0")}`;
  const venture = parse<VentureDossier>(story.opportunity_dossier);
  const build = parse<BuildDossier>(story.build_dossier);
  const vision = venture?.vision ?? null;
  const decided = story.status === "approved" || story.status === "declined";
  const liveUrl = story.deploy_url ?? build?.deploy_url ?? null;

  return (
    <div className="grain relative flex min-h-svh flex-col">
      <header className="border-b hairline">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <Link href="/" aria-label="Back to ProToPro">
              <Wordmark />
            </Link>
            <Link
              href="/#showcase"
              className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist-600 transition-colors hover:text-mist-300"
            >
              / showcase / {id.toLowerCase()}
            </Link>
          </div>
          <span className="rounded-full border hairline px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-500">
            {STAGE_LABEL[story.stage]}
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-16">
        <div className="animate-rise">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-maroon-300">{id}</p>
          <h1 className="mt-4 max-w-3xl text-balance text-4xl leading-tight tracking-[-0.01em] md:text-5xl">
            {story.title}
          </h1>
          {vision?.one_liner && (
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-mist-300">
              <span className="font-display italic text-maroon-300">{vision.product_name}</span>
              {" — "}
              {vision.one_liner}
            </p>
          )}
          {liveUrl && (
            <a
              href={liveUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="ember-gloss mt-8 inline-block rounded-full px-6 py-3 text-sm font-medium text-mist-50 shadow-ember-sm transition-shadow hover:shadow-ember"
            >
              Visit the live product ↗
            </a>
          )}
        </div>

        {/* 1 — the problem */}
        <section className="animate-rise mt-16 [animation-delay:90ms]">
          <SectionLabel>01 · The problem</SectionLabel>
          <div className="glass rounded-2xl p-7">
            <p className="max-w-2xl text-[15px] leading-relaxed text-mist-200">{story.description}</p>
            <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 border-t hairline pt-5">
              <span className="font-mono text-[11px] text-mist-500">
                discovered {new Date(story.discovered_at).toLocaleDateString()}
              </span>
              <a
                href={story.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-[11px] uppercase tracking-[0.12em] text-mist-500 transition-colors hover:text-maroon-300"
              >
                original source ↗
              </a>
            </div>
          </div>
        </section>

        {/* 2 — analyst */}
        <section className="mt-12">
          <SectionLabel>02 · The Analyst&apos;s verdict</SectionLabel>
          <div className="glass rounded-2xl p-7">
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-3xl text-mist-50">{story.score ?? "—"}</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                / 100 conviction
              </span>
            </div>
            {story.reasoning && (
              <p className="mt-4 max-w-2xl text-sm leading-relaxed text-mist-300">{story.reasoning}</p>
            )}
            {venture?.validation?.evidence_summary && (
              <p className="mt-4 max-w-2xl border-t hairline pt-4 text-sm leading-relaxed text-mist-400">
                {venture.validation.evidence_summary}
              </p>
            )}
          </div>
        </section>

        {/* 3 — human gate */}
        <section className="mt-12">
          <SectionLabel>03 · The human decision</SectionLabel>
          <div className="glass rounded-2xl p-7">
            <p className="text-sm leading-relaxed text-mist-300">
              {story.status === "approved"
                ? "Approved for build — a person reviewed the evidence and the Analyst's reasoning, and signed the green light. Nothing here was built without it."
                : story.status === "declined"
                  ? "Rejected at the human gate — the pipeline validated it, a person decided against building it. That is the gate doing its job."
                  : "Awaiting the human gate — shortlisted by the Analyst, not yet decided. Nothing gets built without a person's sign-off."}
            </p>
            {decided && (
              <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                decision: {story.status}
              </p>
            )}
          </div>
        </section>

        {/* 4 — venture pipeline */}
        {vision && (
          <section className="mt-12">
            <SectionLabel>04 · The product vision</SectionLabel>
            <div className="glass rounded-2xl p-7">
              <div className="grid gap-6 md:grid-cols-2">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    value proposition
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-mist-200">{vision.value_proposition}</p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    positioning
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-mist-200">{vision.positioning}</p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    target segment
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-mist-200">{vision.target_segment}</p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    first 90 days
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-mist-200">{vision.execution_strategy}</p>
                </div>
              </div>
              {(vision.differentiation?.length ?? 0) > 0 && (
                <div className="mt-6 border-t hairline pt-5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    durable edges
                  </p>
                  <ul className="mt-3 space-y-2">
                    {vision.differentiation!.map((d) => (
                      <li key={d} className="flex gap-3 text-sm leading-relaxed text-mist-300">
                        <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-maroon-400" />
                        {d}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>
        )}

        {/* 5 — the build */}
        {build && (
          <section className="mt-12">
            <SectionLabel>05 · The build</SectionLabel>
            <div className="glass rounded-2xl p-7">
              {(build.plan?.tech_stack?.length ?? 0) > 0 && (
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    tech stack
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {build.plan!.tech_stack!.map((t) => (
                      <span
                        key={`${t.layer}-${t.choice}`}
                        className="rounded border hairline bg-ink-900 px-2 py-0.5 font-mono text-[10px] tracking-[0.14em] text-mist-500"
                      >
                        {t.layer.toUpperCase()} · {t.choice}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {(build.plan?.features?.length ?? 0) > 0 && (
                <div className="mt-6 border-t hairline pt-5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    shipped features
                  </p>
                  <ul className="mt-3 space-y-2">
                    {build.plan!.features!.map((f) => (
                      <li key={f.name} className="flex gap-3 text-sm leading-relaxed text-mist-300">
                        <span className="mt-0.5 shrink-0 font-mono text-[10px] text-maroon-300">
                          {f.priority}
                        </span>
                        <span>
                          <span className="text-mist-100">{f.name}</span> — {f.description}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(build.qa_reports?.length ?? 0) > 0 && (
                <div className="mt-6 border-t hairline pt-5">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
                    QA rounds
                  </p>
                  <ul className="mt-3 space-y-2">
                    {build.qa_reports!.map((q, i) => (
                      <li key={i} className="text-sm leading-relaxed text-mist-300">
                        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mist-500">
                          round {i + 1} · {q.verdict}
                        </span>{" "}
                        — {q.reasoning}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>
        )}

        {/* 6 — timeline replay */}
        {story.events.length > 0 && (
          <section className="mt-12">
            <SectionLabel>06 · The run, step by step</SectionLabel>
            <ol className="space-y-4 border-l hairline pl-6">
              {story.events.map((e, i) => (
                <li key={i} className="relative">
                  <span className="absolute -left-[29px] top-1.5 h-2 w-2 rounded-full bg-maroon-400" />
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
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-mist-300">{e.message}</p>
                </li>
              ))}
            </ol>
          </section>
        )}

        <p className="mt-16 max-w-lg font-mono text-[11px] leading-relaxed text-mist-600">
          Every step above was executed by the pipeline&apos;s agents and recorded
          as it happened — this page is the durable record of the journey from
          problem to product.
        </p>
      </main>
    </div>
  );
}
