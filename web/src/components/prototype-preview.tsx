import Link from "next/link";
import Image from "next/image";
export function PrototypePreview({
  showNotes = true,
}: {
  showNotes?: boolean;
}) {
  return (
    <section
      aria-labelledby="prototype-preview-title"
      className="mx-auto max-w-6xl px-6 py-24"
    >
      <div className="grid items-center gap-10 md:grid-cols-[1fr_1.15fr]">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-maroon-300">
            01 / A prototype you can use
          </p>
          <h2
            id="prototype-preview-title"
            className="mt-5 text-4xl leading-tight md:text-5xl"
          >
            Useful agents.
            <br />
            <em className="font-display text-maroon-300">
              Deliberate decisions.
            </em>
          </h2>
          <p className="mt-5 leading-relaxed text-mist-300">
            Decision Desk puts a person between an agent’s proposed action and
            permission to act. Inspect the scope, record a reason, and export a
            traceable local review.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-mist-500">
            Handcrafted design reference · fictional requests · no tools
            execute.
          </p>
          <div className="mt-7 flex flex-wrap gap-5">
            <a
              href="/demos/decision-desk/index.html"
              className="ember-gloss rounded-full px-6 py-3 text-sm"
            >
              Open Decision Desk ↗
            </a>
            {showNotes && (
              <Link
                href="/prototypes"
                className="self-center text-sm text-maroon-300"
              >
                Design & verification →
              </Link>
            )}
          </div>
        </div>
        <a
          href="/demos/decision-desk/index.html"
          aria-label="Open the Decision Desk interactive demo"
          className="overflow-hidden rounded-2xl border border-white/15 shadow-2xl"
        >
          <Image
            src="/demos/decision-desk-preview.png"
            alt="Decision Desk: a paper-toned review queue with a forest-green sidebar and a proposal inspector"
            width={1440}
            height={1000}
            className="h-auto w-full"
          />
        </a>
      </div>
    </section>
  );
}
