import { Reveal } from "./reveal";

const STAGES = [
  {
    n: "01",
    name: "Discover",
    agents: ["RESEARCH"],
    body: "The Research Agent works Hacker News and community sources as tools in a reasoning loop — deciding what to search, when to read the full article, and when the signal is strong enough to report.",
  },
  {
    n: "02",
    name: "Validate",
    agents: ["GUARDRAIL", "ANALYST"],
    body: "Candidate ideas pass a configured input check, semantic deduplication and model scoring. These are provisional filters, not proof of customer demand or comprehensive safety.",
  },
  {
    n: "03",
    name: "Approve",
    agents: ["HUMAN"],
    body: "Nothing gets built without a person. Shortlisted problems land in the founder's inbox for sign-off — a deliberate human gate between analysis and execution.",
  },
  {
    n: "04",
    name: "Build",
    agents: ["PM", "ARCHITECT", "ENGINEER", "QA"],
    body: "An approved problem is handed to the build squad: a PM writes the spec, an architect plans the system, files are generated sequentially with sibling-file context, and QA sends weak work back.",
  },
  {
    n: "05",
    name: "Review the artifact",
    agents: ["SHOWCASE"],
    body: "Bound-snapshot builds preserve the approved input. Inspect the actual files and record functional observations before a separate acceptance decision; approval does not automatically publish.",
  },
];

export function Method() {
  return (
    <section id="method" className="relative border-t hairline">
      <div className="mx-auto max-w-6xl px-6 py-28">
        <Reveal>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-maroon-300">
            Method
          </p>
          <h2 className="mt-4 max-w-2xl text-balance text-4xl leading-tight tracking-[-0.01em] md:text-5xl">
            An evidence trail for
            <span className="font-display italic text-maroon-300"> unsolved </span>
            problems
          </h2>
        </Reveal>

        <div className="mt-16">
          {STAGES.map((stage, i) => (
            <Reveal key={stage.n} delay={i * 0.05}>
              <div className="group grid grid-cols-[3.5rem_1fr] gap-6 border-t hairline py-8 transition-colors hover:bg-ink-900/60 md:grid-cols-[6rem_14rem_1fr] md:gap-10 md:px-4">
                <span className="font-mono text-sm text-maroon-400/80 transition-colors group-hover:text-maroon-300">
                  {stage.n}
                </span>
                <h3 className="text-2xl tracking-tight md:text-[1.65rem]">
                  {stage.name}
                </h3>
                <div className="col-span-2 md:col-span-1">
                  <p className="max-w-xl text-[15px] leading-relaxed text-mist-300">
                    {stage.body}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {stage.agents.map((agent) => (
                      <span
                        key={agent}
                        className="rounded border hairline bg-ink-900 px-2 py-0.5 font-mono text-[10px] tracking-[0.14em] text-mist-500"
                      >
                        {agent}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
