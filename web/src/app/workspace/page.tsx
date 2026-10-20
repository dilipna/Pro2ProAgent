"use client";
import { useState } from "react";
import Link from "next/link";
import { ArtifactReview } from "@/components/artifact-review";
import example from "@/data/brief-example.json";
import { parseBrief, downloadBrief, type Brief } from "@/lib/brief";

type Inspection = {
  builds?: { id: string; status: string; acceptance: unknown }[];
  run_id: string;
  status: string;
  pending: { token: string; snapshot_sha256: string; snapshot: unknown }[];
  events: { agent: string; type: string; message: string }[];
};
export default function Workspace() {
  const [brief, setBrief] = useState<Brief | null>(null),
    [raw, setRaw] = useState("");
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [key, setKey] = useState(""),
    [busy, setBusy] = useState(false),
    [inspection, setInspection] = useState<Inspection | null>(null);
  const [localDecision, setLocalDecision] = useState<
      "pending" | "approved" | "rejected"
    >("pending"),
    [localHash, setLocalHash] = useState(""),
    [localConfirmed, setLocalConfirmed] = useState(false);
  const [modelConfigured, setModelConfigured] = useState(false),
    [confirmed, setConfirmed] = useState(false);
  async function load(text: string) {
    setBusy(true);
    try {
      const next = parseBrief(text);
      setBrief(next);
      setRaw(JSON.stringify(next, null, 2));
      setInspection(null);
      setError("");
      setNotice(
        "Brief validated locally. No data was sent and no decision was recorded.",
      );
      setConfirmed(false);
      setLocalConfirmed(false);
      const bytes = await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(JSON.stringify(next)),
      );
      const sha = Array.from(new Uint8Array(bytes))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
      setLocalHash(sha);
      const stored = sessionStorage.getItem(`pro2pro-local-review-${sha}`);
      setLocalDecision(
        stored === "approved" || stored === "rejected" ? stored : "pending",
      );
    } catch (e) {
      setBrief(null);
      setInspection(null);
      setLocalHash("");
      setLocalDecision("pending");
      setNotice("");
      setError(e instanceof Error ? e.message : "Invalid brief");
    } finally {
      setBusy(false);
    }
  }
  function decideLocally(decision: "approved" | "rejected") {
    if (!brief || !localHash || localDecision !== "pending") return;
    if (decision === "approved" && !localConfirmed) {
      setError("Inspect the evidence and scope before recording approval.");
      return;
    }
    try {
      sessionStorage.setItem(`pro2pro-local-review-${localHash}`, decision);
      setLocalDecision(decision);
      setNotice(
        `Local review ${decision}. No backend decision, model call or publication occurred.`,
      );
    } catch {
      setError(
        "Session storage is unavailable; no local decision was recorded.",
      );
    }
  }
  function exportLocalReview() {
    if (!brief || localDecision === "pending") return;
    const record = {
      mode: "local_rehearsal",
      decision: localDecision,
      brief_sha256: localHash,
      recorded_at: new Date().toISOString(),
      brief,
      authority:
        "Browser-session rehearsal only. This record cannot authorize a backend build.",
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "pro2pro-local-review.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  async function api(path: string, body?: unknown) {
    const r = await fetch(`/api/workspace/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "Content-Type": "application/json",
        ...(key ? { Authorization: `Bearer ${key}` } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const d = await r.json();
    if (!r.ok)
      throw new Error(
        typeof d.detail === "string"
          ? d.detail
          : "The API rejected this request. Check the brief contract and operator key.",
      );
    return d;
  }
  async function action(kind: "import" | "approve" | "reject" | "execute") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!brief) throw new Error("Load a problem brief first.");
      let run = inspection?.run_id;
      if (kind === "import") {
        const imported = await api("briefs/import", brief);
        run = imported.run_id;
        const cfg = await api("workspace/config");
        setModelConfigured(cfg.model_configured === true);
        setNotice(
          imported.created
            ? "Imported into the real operator queue. No model called."
            : "This exact brief is already in the queue; no duplicate was created.",
        );
      } else if (kind === "execute") {
        await api(`briefs/${run}/execute`, {});
        setNotice(
          "Execution claimed. Inspect progress and failures in the operations console.",
        );
      } else {
        const review = inspection?.pending[0];
        if (!review) throw new Error("No pending review is available.");
        if (kind === "approve" && !confirmed)
          throw new Error(
            "Confirm that you inspected the evidence and exact scope.",
          );
        await api(`reviews/${review.token}`, {
          decision: kind,
          snapshot_sha256: review.snapshot_sha256,
        });
        setNotice(
          kind === "approve"
            ? "This exact snapshot is approved. Building remains a separate action."
            : "Rejected. No build was started.",
        );
      }
      setInspection(await api(`briefs/${run}`));
      setConfirmed(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="journey">
      <header className="journey-nav">
        <Link href="/" className="journey-brand">
          Pro<span>To</span>Pro <small>/ build with evidence</small>
        </Link>
        <nav aria-label="Workspace navigation">
          <Link href="/console">Operations</Link>
          <Link href="/discover">XploreMore workbench</Link>
          <a href="https://github.com/dilipna/Pro2ProAgent">Source ↗</a>
        </nav>
      </header>
      <main>
        <section className="journey-intro">
          <p className="journey-kicker">CONNECTED WORKFLOW / 02</p>
          <h1>
            Keep the evidence.
            <br />
            <em>Make the decision.</em>
          </h1>
          <p>
            A reported problem becomes a bounded specification. Review what the
            prototype should do before a model builds anything.
          </p>
          <div className="journey-steps" aria-label="Problem to product stages">
            <span>
              01 <b>XploreMore evidence</b>
            </span>
            <span className="active">
              02 <b>Human scope review</b>
            </span>
            <span>
              03 <b>Pro2Pro build</b>
            </span>
            <span>
              04 <b>Tests & acceptance</b>
            </span>
          </div>
        </section>
        <div className="journey-toolbar">
          <div>
            <span className="journey-kicker">START WITH A BRIEF</span>
            <h2>A reviewable handoff.</h2>
          </div>
          <div className="journey-buttons">
            <button
              onClick={() => load(JSON.stringify(example))}
              disabled={busy}
            >
              Inspect recorded example
            </button>
            <label className="journey-file">
              Import brief JSON
              <input
                type="file"
                accept=".json,application/json"
                disabled={busy}
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (f) {
                    if (f.size > 64000) {
                      setBrief(null);
                      setInspection(null);
                      setLocalHash("");
                      setLocalDecision("pending");
                      setNotice("");
                      setError("Keep the brief below 64 KB.");
                      return;
                    }
                    load(await f.text());
                  }
                }}
              />
            </label>
          </div>
        </div>
        <p className="journey-note">
          The example is a historical XploreMore record, with a sample
          specification. Loading it performs local validation only. Source
          reports remain untrusted evidence; usefulness is unverified.
        </p>
        {error && (
          <p role="alert" className="journey-error">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="journey-notice">
            {notice}
          </p>
        )}
        {!brief ? (
          <div className="journey-empty">
            <span>YOUR NEXT BUILD STARTS HERE</span>
            <h2>
              A source, a scope,
              <br />
              and a reason to build.
            </h2>
            <p>
              Open the recorded example or bring a brief exported from
              XploreMore. The evidence stays beside the acceptance criteria
              throughout the review.
            </p>
            <div className="journey-orbit" aria-hidden="true">
              <i />
              <i />
              <b>
                HUMAN
                <br />
                JUDGMENT
              </b>
            </div>
          </div>
        ) : (
          <div className="journey-grid">
            <section className="journey-panel">
              <p className="journey-kicker">01 / SOURCE EVIDENCE</p>
              <h2>{brief.source.statement}</h2>
              <div className="journey-metrics">
                <span>
                  <b>{brief.source.voice_count}</b> reported voice(s)
                </span>
                <span>
                  <b>{brief.source.source_count}</b> source(s)
                </span>
                <span>
                  <b>#{brief.source.problem_id}</b> problem identity
                </span>
              </div>
              <p className="journey-note">
                Snapshot: {brief.source.captured_at}
              </p>
              {brief.source.evidence.map((e, i) => (
                <article className="journey-evidence" key={i}>
                  <span>E{i + 1} / PUBLIC REPORT</span>
                  <blockquote>{e.excerpt}</blockquote>
                  <a href={e.url} target="_blank" rel="noreferrer">
                    Inspect original source ↗
                  </a>
                </article>
              ))}
              <p className="journey-note">{brief.source.limitations}</p>
            </section>
            <section className="journey-panel">
              <p className="journey-kicker">02 / EXACT BUILD SCOPE</p>
              <h2>{brief.spec.goal}</h2>
              <p className="journey-note">
                For {brief.spec.target_user} · browser-only delivery
              </p>
              <h3>Included in this prototype</h3>
              <ul>
                {brief.spec.in_scope.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              <h3>Explicitly out of scope</h3>
              <ul>
                {brief.spec.out_of_scope.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              <h3>Acceptance criteria</h3>
              <ol className="journey-criteria">
                {brief.spec.acceptance.map((c, i) => (
                  <li key={i}>
                    <span>CHECK {String(i + 1).padStart(2, "0")}</span>
                    <p>
                      <b>Given</b> {c.given}
                      <br />
                      <b>When</b> {c.when}
                      <br />
                      <b>Then</b> {c.then}
                    </p>
                  </li>
                ))}
              </ol>
              <button onClick={() => downloadBrief(brief)}>
                Export this brief ↓
              </button>
            </section>
          </div>
        )}
        {brief && (
          <section className="journey-panel journey-review">
            <p className="journey-kicker">HUMAN DECISION / LOCAL REHEARSAL</p>
            <h2>Practice the decision before connecting an operator.</h2>
            <p className="journey-note">
              This working review stays in this browser session. It cannot
              authorize a server build and is not a recorded operator approval.
              Loading or opening the brief never approves it.
            </p>
            <div className="journey-status">
              <span>LOCAL REVIEW</span>
              <strong>{localDecision}</strong>
            </div>
            {localDecision === "pending" ? (
              <>
                <label className="journey-check">
                  <input
                    type="checkbox"
                    checked={localConfirmed}
                    onChange={(e) => setLocalConfirmed(e.target.checked)}
                  />
                  I inspected the evidence, scope and each acceptance criterion.
                </label>
                <div className="journey-buttons">
                  <button
                    disabled={!localConfirmed || busy}
                    onClick={() => decideLocally("approved")}
                  >
                    Record local approval
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => decideLocally("rejected")}
                  >
                    Reject locally
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="journey-note">
                  This session already recorded a decision for this brief
                  checksum. Reloading the same brief preserves it. A revised
                  brief has a new checksum.
                </p>
                <button onClick={exportLocalReview}>
                  Export local review record ↓
                </button>
              </>
            )}
          </section>
        )}
        <section className="journey-connect">
          <div>
            <p className="journey-kicker">OPERATOR CONNECTION</p>
            <h2>Turn a local review into a recorded decision.</h2>
            <p className="journey-note">
              Your key is held in this page’s memory and sent only to this
              site’s configured operator API. Import and approval do not invoke
              models or send email. Generation requires a configured provider
              and a separate action.
            </p>
          </div>
          <div className="journey-key">
            <label htmlFor="operator">Operator key</label>
            <input
              id="operator"
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              autoComplete="off"
              placeholder="Required by the operator API"
            />
            <button
              disabled={!brief || !key || busy}
              onClick={() => void action("import")}
            >
              {busy ? "Working…" : "Import into review queue →"}
            </button>
          </div>
        </section>
        {inspection && (
          <section className="journey-panel journey-review">
            <div className="journey-status">
              <span>BACKEND RECORD</span>
              <strong>{inspection.status.replaceAll("_", " ")}</strong>
              <code>{inspection.run_id}</code>
            </div>
            {inspection.pending[0] && (
              <>
                <p className="journey-note">
                  Approval is bound to SHA-256{" "}
                  <code>{inspection.pending[0].snapshot_sha256}</code>. Editing
                  the brief creates a different review.
                </p>
                <label className="journey-check">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  I inspected the source evidence, scope and acceptance criteria
                  above.
                </label>
                <div className="journey-buttons">
                  <button
                    disabled={!confirmed || busy}
                    onClick={() => void action("approve")}
                  >
                    Approve this snapshot
                  </button>
                  <button disabled={busy} onClick={() => void action("reject")}>
                    Reject proposal
                  </button>
                </div>
              </>
            )}
            {inspection.status === "ready_to_build" && (
              <>
                <p>
                  The approved brief is preserved.{" "}
                  {modelConfigured
                    ? "A model is configured; availability remains unverified."
                    : "No model is configured. The brief stays ready without spending tokens."}
                </p>
                <button
                  disabled={!modelConfigured || busy}
                  onClick={() => void action("execute")}
                >
                  Start configured model build
                </button>
              </>
            )}
            <ol className="journey-timeline">
              {inspection.events.map((e, i) => (
                <li key={i}>
                  <span>{e.agent}</span>
                  <p>{e.message}</p>
                </li>
              ))}
            </ol>
            <Link href={`/console/runs/${inspection.run_id}`}>
              Open full operations record →
            </Link>
          </section>
        )}
        {inspection?.builds
          ?.filter((b) => b.status === "complete")
          .map((b) => (
            <ArtifactReview key={b.id} buildId={b.id} operatorKey={key} />
          ))}
        {inspection && (
          <button
            disabled={busy}
            onClick={async () => {
              try {
                setInspection(await api(`briefs/${inspection.run_id}`));
              } catch (e) {
                setError(e instanceof Error ? e.message : "Refresh failed");
              }
            }}
          >
            Refresh backend progress
          </button>
        )}
        <details className="journey-json">
          <summary>Inspect or edit the handoff JSON</summary>
          <label htmlFor="brief-json">Problem brief JSON</label>
          <textarea
            id="brief-json"
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            rows={12}
          />
          <button onClick={() => load(raw)} disabled={busy}>
            Validate as a new local brief
          </button>
        </details>
        <section className="journey-boundaries">
          <h2>What counts as done?</h2>
          <div>
            <article>
              <span>BUILD</span>
              <h3>A generated artifact is a candidate.</h3>
              <p>
                The approved snapshot travels into venture analysis and the
                build dossier. Model review alone does not establish a working
                product.
              </p>
            </article>
            <article>
              <span>VERIFY</span>
              <h3>Test the promised behavior.</h3>
              <p>
                Check inputs, outputs, failure cases and browser interaction
                independently. Record what was exercised and what remains
                unknown.
              </p>
            </article>
            <article>
              <span>ACCEPT</span>
              <h3>Review the actual result.</h3>
              <p>
                Approval of a problem does not authorize publication of an
                unseen generated artifact. New bound-snapshot builds withhold
                automatic publication.
              </p>
            </article>
          </div>
        </section>
      </main>
      <footer className="journey-footer">
        <span>Built by Dilip Nallamasa · XploreMore × Pro2Pro</span>
        <a href="https://github.com/dilipna/Pro2ProAgent/blob/master/docs/evidence-to-product.md">
          Architecture & evidence ↗
        </a>
      </footer>
    </div>
  );
}
