import Link from "next/link";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { PrototypePreview } from "@/components/prototype-preview";
export const metadata = {
  title: "Decision Desk — working prototype | ProToPro",
  description:
    "Try a browser-local action review prototype. Inspect fictional agent requests, record decisions and export a review trail.",
};
export default function Prototypes() {
  return (
    <>
      <Nav />
      <main className="flex-1 pt-32">
        <div className="mx-auto max-w-6xl px-6">
          <p className="font-mono text-xs uppercase tracking-widest text-maroon-300">
            Prototype studio / browser edition
          </p>
          <h1 className="mt-5 max-w-4xl text-5xl leading-tight md:text-7xl">
            A small product.
            <br />
            <em className="font-display text-maroon-300">
              A complete interaction.
            </em>
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-mist-300">
            Experience the design standard the build pipeline aims for: a
            specific workflow, useful states, a distinct visual direction and
            behavior you can inspect.
          </p>
        </div>
        <PrototypePreview showNotes={false} />
        <section className="mx-auto grid max-w-6xl gap-8 px-6 pb-24 md:grid-cols-3">
          {[
            [
              "01 / Inspect",
              "Read before you decide.",
              "Choose a fictional request. Inspect its tool, risk, scope and proposed input. Try filtering the queue or searching for an action.",
            ],
            [
              "02 / Review",
              "Make the reason explicit.",
              "Approve or decline with a required note. Revisit the reviewed proposal, refresh the page and check the preserved decision.",
            ],
            [
              "03 / Verify",
              "Take the record with you.",
              "Export the JSON review trail. Start with an empty workspace or reset the examples. Records stay in this browser profile; clearing site data removes them.",
            ],
          ].map(([n, h, p]) => (
            <article key={n} className="glass rounded-2xl p-7">
              <p className="font-mono text-xs uppercase text-maroon-300">{n}</p>
              <h2 className="mt-4 text-2xl">{h}</h2>
              <p className="mt-4 text-sm leading-relaxed text-mist-300">{p}</p>
            </article>
          ))}
          <div className="rounded-2xl border border-white/15 p-8 md:col-span-3">
            <h2 className="text-2xl">What this demonstrates</h2>
            <p className="mt-4 max-w-3xl leading-relaxed text-mist-300">
              This is a handcrafted reference, not an AI-generated result or a
              measured improvement in generated quality. The demo runs without a
              backend, credentials or model calls. Local decisions never
              authorize a real system. Browser storage is for non-sensitive
              demonstration notes.
            </p>
            <p className="mt-4 max-w-3xl leading-relaxed text-mist-300">
              The separate build pipeline now requires a product design contract
              and blocks major QA issues. Its optional browser reviewer checks
              responsive layout, runtime errors and declared interaction
              scenarios against exported source. Passing those checks
              establishes only the behavior exercised.
            </p>
            <div className="mt-6 flex flex-wrap gap-6 text-sm text-maroon-300">
              <Link href="/engineering">Explore the engineering →</Link>
              <Link href="/workspace">Review a problem brief →</Link>
              <a href="https://github.com/dilipna/Pro2ProAgent/tree/improve/evidence-to-product/examples/decision-desk">
                Inspect reference source ↗
              </a>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
