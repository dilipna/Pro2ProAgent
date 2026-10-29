import Link from "next/link";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";

export const metadata = {
  title: "Engineering the evidence trail — ProToPro",
  description: "Snapshot-bound approval, persisted execution and real process-recovery tests for evidence-led prototype delivery.",
};

const boundaries = [
  ["Evidence", "Original public report, source links and limitations", "An observed report does not prove market demand."],
  ["Review", "A human decision bound to an exact scope snapshot", "A browser rehearsal cannot authorize a server build."],
  ["Execution", "Persisted job, stable identities and graph checkpoints", "An interrupted node may repeat a provider request."],
  ["Acceptance", "Generated source, artifact hash and recorded observations", "Model-written QA does not prove functional behavior."],
];
const experiments = [
  ["Before the worker starts", "Keep the claimed job queued across startup."],
  ["After a venture checkpoint", "Resume the existing opportunity; preserve saved evidence."],
  ["Between venture and build", "Keep the completed dossier and assign one build identity."],
  ["After a build checkpoint", "Preserve completed generated files and resume the same build."],
  ["After artifact persistence", "Reuse the saved artifact instead of generating a replacement."],
];

export default function Engineering() {
 return <><Nav /><main className="engineering-page mx-auto w-full max-w-6xl px-6 pb-24 pt-44">
  <p className="font-mono text-xs uppercase tracking-[0.18em] text-maroon-300">Engineering / evidence to artifact</p>
  <h1 className="mt-6 max-w-4xl text-5xl leading-tight tracking-tight md:text-7xl">Build a prototype.<br /><em className="font-display text-maroon-300">Keep the argument.</em></h1>
  <p className="mt-8 max-w-2xl text-lg leading-relaxed text-mist-300">ProToPro connects a reported problem to a bounded product brief, an explicit human decision and an inspectable generated result. The engineering challenge is preserving that chain through failures.</p>
  <div className="mt-8 flex flex-wrap gap-4 text-sm"><Link className="ember-gloss rounded-full px-5 py-3" href="/discover">Explore the recorded journey →</Link><a className="glass rounded-full px-5 py-3" href="https://github.com/dilipna/Pro2ProAgent">Inspect the source ↗</a></div>
  <section className="mt-20" aria-labelledby="architecture-heading">
   <h2 id="architecture-heading" className="text-3xl">Four boundaries. One traceable record.</h2>
   <ol className="mt-8 grid gap-4 md:grid-cols-4">{boundaries.map(([name,mechanism,limit],index)=><li key={name} className="glass rounded-2xl p-6"><span className="font-mono text-xs text-maroon-300">0{index+1} / {name.toUpperCase()}</span><h3 className="mt-4 text-lg">{mechanism}</h3><p className="mt-4 text-sm leading-relaxed text-mist-500">{limit}</p></li>)}</ol>
  </section>
  <section className="mt-20 grid gap-10 md:grid-cols-2">
   <div><p className="font-mono text-xs uppercase tracking-widest text-maroon-300">Decision / durable execution</p><h2 className="mt-4 text-3xl">Recover the work.<br />Preserve its identity.</h2><p className="mt-6 leading-relaxed text-mist-300">Execution admission commits the run claim and job together. The job retains its opportunity and build identities; venture and build graphs save synchronous SQLite checkpoints. A same-host kernel lock prevents competing imported-brief workers.</p><p className="mt-4 leading-relaxed text-mist-300">Before recovery, the worker checks the approved input and its code/runtime fingerprint. Changed input or incompatible code stops execution for review. Missing model configuration leaves queued work inspectable.</p></div>
   <div className="glass rounded-2xl p-7"><h3 className="text-xl">The storage contract matters.</h3><p className="mt-4 leading-relaxed text-mist-300">This is a single-host design with persistent database and checkpoint files. Ephemeral cloud storage cannot satisfy that contract. The system does not claim distributed scheduling or exactly-once billing.</p><p className="mt-4 leading-relaxed text-mist-300">A provider response interrupted before checkpoint persistence can be requested again. Legacy discovery-triggered execution retains its earlier recovery behavior; the new guarantee applies to imported approved briefs.</p></div>
  </section>
  <section className="mt-20" aria-labelledby="campaign-heading"><p className="font-mono text-xs uppercase tracking-widest text-maroon-300">Validation / actual process termination</p><h2 id="campaign-heading" className="mt-4 text-3xl">A restart assertion is not a restart experiment.</h2><p className="mt-5 max-w-3xl leading-relaxed text-mist-300">The local campaign kills a real worker process at each boundary, then starts a new process against the same isolated storage. Deterministic model fixtures exercise the production graphs without provider calls, email or publication.</p><div className="mt-8 divide-y divide-white/10 border-y border-white/10">{experiments.map(([point,invariant],index)=><article className="grid gap-3 py-5 md:grid-cols-[3rem_1fr_1.3fr]" key={point}><span className="font-mono text-sm text-maroon-300">0{index+1}</span><h3>{point}</h3><p className="text-sm leading-relaxed text-mist-300">{invariant}</p></article>)}</div><p className="mt-5 max-w-3xl text-sm leading-relaxed text-mist-500">Additional tests cover live worker contention, concurrent HTTP admission, changed approval, code identity and terminal graph failures. Receipts retain identities, checkpoint counts, call sequences and artifact hashes. These fixtures establish recovery behavior, not generated-product quality.</p></section>
  <section className="mt-20"><p className="font-mono text-xs uppercase text-maroon-300">Design contract / independent browser review</p><h2 className="mt-4 text-3xl">Make the product specific. Exercise the result.</h2><p className="mt-5 max-w-3xl leading-relaxed text-mist-300">New browser builds require a primary workflow, layout, visual direction, signature detail, interface states and responsive rules before engineering begins. Major and critical QA findings block completion. A source audit checks a limited structural floor; it does not judge visual quality.</p><p className="mt-4 max-w-3xl leading-relaxed text-mist-300">The optional browser reviewer serves exported files in an isolated local session, blocks external requests and exercises declared scenarios at desktop, tablet and mobile widths. Decision Desk is the handcrafted reference for this workflow. It is not an AI output benchmark.</p><div className="mt-6 flex flex-wrap gap-6 text-sm text-maroon-300"><Link href="/prototypes">Try the working reference →</Link><a href="https://github.com/dilipna/Pro2ProAgent/actions/runs/39756512450">Previous design-gate CI evidence ↗</a></div><p className="mt-4 text-sm text-mist-500">Public browser edition: no backend calls. Full execution: explicit connected mode, authenticated local backend and persistent storage. Provider-funded generation has not been benchmarked in this release.</p></section>
  <section className="mt-20 rounded-2xl border border-maroon-700/50 p-8"><h2 className="text-3xl">What still needs independent evidence?</h2><div className="mt-6 grid gap-7 md:grid-cols-3"><div><h3 className="text-maroon-300">Functional quality</h3><p className="mt-3 text-sm leading-relaxed text-mist-300">Generated files and model reviews need actual behavior tests against the approved criteria. Operator observations are recorded assertions.</p></div><div><h3 className="text-maroon-300">Cost enforcement</h3><p className="mt-3 text-sm leading-relaxed text-mist-300">Recorded estimated spend is not an atomic per-call reservation or guaranteed dollar ceiling. No paid model benchmark was run for recovery validation.</p></div><div><h3 className="text-maroon-300">Remote availability</h3><p className="mt-3 text-sm leading-relaxed text-mist-300">The public recorded walkthrough works without a live API. Authenticated operation depends on a separately available backend with suitable persistent storage.</p></div></div></section>
 </main><Footer /></>;
}
