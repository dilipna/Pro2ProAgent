"use client";

import { useState } from "react";
import Link from "next/link";
import example from "@/data/brief-example.json";

const stages = ["Evidence", "Scope", "Decision", "Artifact"];

export function EvidencePreview() {
  const [stage, setStage] = useState(0);
  return (
    <section className="evidence-preview" aria-labelledby="evidence-preview-title">
      <div className="evidence-preview-heading">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-maroon-300">XploreMore × ProToPro</p>
          <h2 id="evidence-preview-title">Follow one problem.<br /><em>Keep every decision visible.</em></h2>
        </div>
        <p>A recorded source. A bounded brief. An explicit review. Explore the contract before entering the workspace.</p>
      </div>
      <div className="evidence-preview-shell">
        <div role="tablist" aria-label="Evidence to artifact walkthrough" className="evidence-preview-tabs">
          {stages.map((label, index) => (
            <button key={label} id={`journey-tab-${index}`} role="tab" aria-selected={stage === index}
              aria-controls={`journey-panel-${index}`} tabIndex={stage === index ? 0 : -1}
              onClick={() => setStage(index)}
              onKeyDown={(event) => {
                let next = stage;
                if (event.key === "ArrowRight") next = (stage + 1) % stages.length;
                else if (event.key === "ArrowLeft") next = (stage + stages.length - 1) % stages.length;
                else if (event.key === "Home") next = 0;
                else if (event.key === "End") next = stages.length - 1;
                else return;
                event.preventDefault(); setStage(next);
                document.getElementById(`journey-tab-${next}`)?.focus();
              }}><span>0{index + 1}</span>{label}</button>
          ))}
        </div>
        <div id={`journey-panel-${stage}`} role="tabpanel" aria-labelledby={`journey-tab-${stage}`} tabIndex={0} className="evidence-preview-panel">
          {stage === 0 && <>
            <p className="evidence-preview-label">RECORDED REPORT / #{example.source.problem_id}</p>
            <h3>{example.source.statement}</h3>
            <blockquote>{example.source.evidence[0].excerpt}</blockquote>
            <a href={example.source.evidence[0].url} target="_blank" rel="noreferrer">Read the original issue ↗</a>
            <p className="evidence-preview-note">{example.source.voice_count} reported voice · {example.source.source_count} source · Historical snapshot, not validated demand.</p>
          </>}
          {stage === 1 && <>
            <p className="evidence-preview-label">PROPOSED SCOPE / BROWSER-ONLY PROTOTYPE</p>
            <h3>{example.spec.goal}</h3>
            <div className="evidence-preview-columns"><div><h4>Include</h4><ul>{example.spec.in_scope.map(item => <li key={item}>{item}</li>)}</ul></div><div><h4>Exclude</h4><ul>{example.spec.out_of_scope.map(item => <li key={item}>{item}</li>)}</ul></div></div>
            <p className="evidence-preview-note">{example.spec.acceptance.length} observable acceptance criteria travel with the source. Edit them in discovery before review.</p>
          </>}
          {stage === 2 && <>
            <p className="evidence-preview-label">HUMAN REVIEW / EXACT SNAPSHOT</p>
            <h3>Make the decision before the build.</h3>
            <p>The operator reviews the evidence and scope together. Approval is tied to that precise snapshot; changing it invalidates the approved input.</p>
            <div className="evidence-preview-gate"><span aria-hidden="true">◇</span><div><strong>Awaiting a human decision</strong><p>This walkthrough grants no approval. The workspace offers a local rehearsal and a separate authenticated operator path.</p></div></div>
          </>}
          {stage === 3 && <>
            <p className="evidence-preview-label">ARTIFACT / SEPARATE ACCEPTANCE</p>
            <h3>A generated result still needs evidence.</h3>
            <p>Keep the approved brief next to the generated files and their artifact hash. Inspect each acceptance criterion before recording an operator assessment.</p>
            <div className="evidence-preview-gate"><span aria-hidden="true">↳</span><div><strong>Publication remains a separate decision</strong><p>Model-written QA and operator assertions do not establish independently tested behavior. No generated artifact is published by this walkthrough.</p></div></div>
          </>}
        </div>
        <div className="evidence-preview-bottom"><span>RECORDED WALKTHROUGH · NO MODEL CALLS</span><Link href="/discover">Shape this brief →</Link></div>
      </div>
    </section>
  );
}
