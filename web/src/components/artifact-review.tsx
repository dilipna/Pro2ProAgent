"use client";
import { useState } from "react";
type Artifact = {
  build_id: string;
  artifact_sha256: string;
  files: { path: string; content: string }[];
  approved_snapshot: {
    content: {
      brief: {
        spec: { acceptance: { given: string; when: string; then: string }[] };
      };
    };
  };
  acceptance: unknown;
};
export function ArtifactReview({
  buildId,
  operatorKey,
}: {
  buildId: string;
  operatorKey: string;
}) {
  const [artifact, setArtifact] = useState<Artifact | null>(null),
    [error, setError] = useState("");
  const [observations, setObservations] = useState<string[]>([]),
    [passed, setPassed] = useState<boolean[]>([]),
    [method, setMethod] = useState("");
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  async function request(path: string, body?: unknown) {
    const r = await fetch(`/api/workspace/builds/${buildId}/${path}`, {
      method: body ? "POST" : "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${operatorKey}`,
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Artifact request failed");
    return d;
  }
  async function load() {
    setBusy(true);
    try {
      const a = await request("artifact");
      setArtifact(a);
      setObservations(
        a.approved_snapshot?.content?.brief?.spec?.acceptance.map(() => "") ||
          [],
      );
      setPassed(
        a.approved_snapshot?.content?.brief?.spec?.acceptance.map(
          () => false,
        ) || [],
      );
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to inspect artifact");
    } finally {
      setBusy(false);
    }
  }
  async function decide(decision: "accept" | "reject") {
    if (!artifact) return;
    setBusy(true);
    setError("");
    try {
      await request("accept", {
        artifact_sha256: artifact.artifact_sha256,
        decision,
        method,
        checks: observations.map((observation, criterion) => ({
          criterion,
          passed: passed[criterion],
          observation,
        })),
      });
      setNotice(
        `Artifact ${decision === "accept" ? "accepted" : "rejected"}. No publication was started.`,
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  }
  function download() {
    if (!artifact) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(artifact, null, 2)], {
        type: "application/json",
      }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "pro2pro-artifact-review.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="journey-panel" style={{ marginTop: 24 }}>
      <p className="journey-kicker">04 / REVIEW THE ACTUAL ARTIFACT</p>
      <h2>Generation is a proposal. Acceptance needs evidence.</h2>
      <button onClick={() => void load()} disabled={busy}>
        Inspect candidate files & checks
      </button>
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
      {artifact && (
        <>
          <p className="journey-note">
            Artifact SHA-256: <code>{artifact.artifact_sha256}</code>. This page
            displays source; it does not execute generated code. Perform
            functional checks separately and record concrete observations. The
            server records operator assertions, not independent proof.
          </p>
          {artifact.files.map((f) => (
            <details className="journey-json" key={f.path}>
              <summary>{f.path}</summary>
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  overflowWrap: "anywhere",
                  fontSize: 12,
                }}
              >
                {f.content}
              </pre>
            </details>
          ))}
          <button onClick={download}>Export source & review context ↓</button>
          {artifact.acceptance ? (
            <p className="journey-note">
              A decision is already recorded for this immutable artifact.
            </p>
          ) : (
            <>
              <label
                style={{ display: "block", marginTop: 24 }}
                htmlFor="test-method"
              >
                How did you test this artifact?
              </label>
              <textarea
                id="test-method"
                maxLength={1000}
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                placeholder="Browser/environment, test steps and saved evidence"
              />
              {artifact.approved_snapshot?.content?.brief?.spec?.acceptance.map(
                (c, i) => (
                  <div className="journey-evidence" key={i}>
                    <p className="journey-note">
                      Given {c.given} · When {c.when} · Then {c.then}
                    </p>
                    <label htmlFor={`observation-${i}`}>
                      Observed result for check {i + 1}
                    </label>
                    <textarea
                      id={`observation-${i}`}
                      maxLength={1000}
                      value={observations[i] || ""}
                      onChange={(e) =>
                        setObservations(
                          observations.map((v, j) =>
                            i === j ? e.target.value : v,
                          ),
                        )
                      }
                    />
                    <label className="journey-check">
                      <input
                        type="checkbox"
                        checked={passed[i] || false}
                        onChange={(e) =>
                          setPassed(
                            passed.map((v, j) =>
                              i === j ? e.target.checked : v,
                            ),
                          )
                        }
                      />
                      This criterion passed when tested.
                    </label>
                  </div>
                ),
              )}
              <div className="journey-buttons">
                <button
                  disabled={
                    busy ||
                    !method.trim() ||
                    !observations.length ||
                    observations.some((x) => !x.trim()) ||
                    passed.some((x) => !x)
                  }
                  onClick={() => void decide("accept")}
                >
                  Accept tested artifact
                </button>
                <button
                  disabled={
                    busy ||
                    !method.trim() ||
                    !observations.length ||
                    observations.some((x) => !x.trim())
                  }
                  onClick={() => void decide("reject")}
                >
                  Reject with observations
                </button>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
