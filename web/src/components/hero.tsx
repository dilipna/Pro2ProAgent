import { getIdeas } from "@/lib/api";
import { DISCOVERY_FEED } from "@/lib/cases";

/**
 * Live idea titles from the pipeline; the seeded feed when the API is
 * down or has too few items for the marquee to loop without a visible
 * gap.
 */
async function loadFeed(): Promise<string[]> {
  const ideas = await getIdeas();
  if (!ideas || ideas.length < 6) return DISCOVERY_FEED;
  return ideas.slice(0, 12).map((idea) => idea.title);
}

async function DiscoveryTicker() {
  const feed = await loadFeed();
  // Duplicated list yields a seamless -50% translate loop.
  const items = [...feed, ...feed];
  return (
    <div className="ticker-mask w-full overflow-hidden border-y hairline py-3.5">
      <div className="animate-ticker flex w-max items-center gap-10">
        {items.map((item, i) => (
          <span
            key={i}
            className="flex shrink-0 items-center gap-3 font-mono text-[11px] uppercase tracking-[0.12em] text-mist-500"
            aria-hidden={i >= feed.length}
          >
            <span className="h-1 w-1 rounded-full bg-maroon-400" />
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

export function Hero() {
  return (
    <section className="grain relative flex min-h-svh flex-col justify-end overflow-hidden">
      {/* Ember glow rising from below the fold */}
      <div
        aria-hidden
        className="animate-ember absolute left-1/2 top-[62%] h-[80vh] w-[120vw] -translate-x-1/2 rounded-[100%]"
        style={{
          background:
            "radial-gradient(closest-side, rgba(160,34,64,0.28) 0%, rgba(111,26,46,0.14) 45%, transparent 72%)",
        }}
      />
      {/* Faint vertical hairlines — a stage, not a void */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.05]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(to right, transparent, transparent calc(100%/6 - 1px), #f6f1f2 calc(100%/6 - 1px), #f6f1f2 calc(100%/6))",
        }}
      />

      {/* CSS-only entrances: hero text must be visible without waiting on
          hydration — better LCP, and robust in crawlers/headless browsers. */}
      <div className="relative mx-auto w-full max-w-6xl px-6 pb-20 pt-40">
        <p className="animate-rise mb-8 flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.18em] text-maroon-300">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-maroon-400" />
          An autonomous product company
        </p>

        <h1 className="animate-rise max-w-4xl text-balance text-[clamp(2.75rem,7.5vw,5.5rem)] leading-[1.02] tracking-[-0.02em] [animation-delay:90ms]">
          Problems in.
          <br />
          <span className="font-display italic text-maroon-300">Products</span> out.
        </h1>

        <p className="animate-rise mt-8 max-w-xl text-pretty text-lg leading-relaxed text-mist-300 [animation-delay:180ms]">
          ProToPro listens to real pain points across developer communities,
          validates them with guardrails and analysis, and ships working
          solutions — a company of AI agents, with a human signing every
          green light.
        </p>

        <div className="animate-rise mt-10 flex flex-wrap items-center gap-4 [animation-delay:270ms]">
          <a
            href="#showcase"
            className="ember-gloss rounded-full px-6 py-3 text-sm font-medium text-mist-50 shadow-ember-sm transition-shadow hover:shadow-ember"
          >
            Explore the showcase
          </a>
          <a
            href="#method"
            className="glass rounded-full px-6 py-3 text-sm text-mist-300 transition-colors hover:text-mist-50"
          >
            How it works
          </a>
        </div>
      </div>

      <div className="relative">
        <p className="mx-auto max-w-6xl px-6 pb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-mist-600">
          Live from discovery
        </p>
        <DiscoveryTicker />
      </div>
    </section>
  );
}
