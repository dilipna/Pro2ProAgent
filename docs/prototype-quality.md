# Prototype quality: design first, independent evidence second

## The defect and repair

The earlier generator requested a distinct visual identity in prose, but its gate
ignored `needs_revision` and major issues. Substantial usability repairs could be
requested while the graph still marked a build complete. Completion now requires
an approved verdict with no critical or major findings. Minor polish remains
visible. The existing two QA rounds (one repair) are unchanged.

The existing architect call now produces a bounded `ProductDesign` contract:

- Primary workflow and useful result.
- Named layout regions and their hierarchy.
- Specific visual direction: palette, typography, spacing and density.
- One useful signature detail within the approved scope.
- Initial, empty, invalid and completed states.
- Mobile reflow and keyboard/touch behavior.

Every file generator receives the same contract and complete existing sibling
files. Choose an inspector, ledger, editor or other workspace that fits the task;
charts and KPI tiles aren't intrinsically valuable. Label example data, preserve
an intentionally empty workspace, and provide recovery paths. A three-file static
app can be polished without a framework migration or extra provider calls.

New browser architectures missing the contract stop before engineering. Historical
dossiers remain readable without invented design evidence. Browser component sets
now always include a stylesheet.

## Source checks and bounded repair

`build/quality.py` adds deterministic findings independently of the model verdict.
For the new design contract it checks nonempty HTML/CSS/JS, title/language/viewport,
one h1 and main region, duplicate ids, associated control labels, CSS tokens,
responsive/focus rules and missing static DOM ids. Findings name the component
and actionable fix. CSS comments cannot masquerade as implemented rules.

This is a minimum source floor, not visual quality or WCAG conformance. A media
query does not prove good mobile layout. Model source review additionally compares
the implementation to the design contract, but cannot claim screenshots or runtime
observations. Dossiers explicitly state the verification scope.

Major findings now participate in targeted repair. Markup revisions carry dependent
styles and logic through sequential regeneration against the new markup. Remaining
problems after the fixed round limit surface as `needs_revision`.

This changes the backend execution fingerprint. An older interrupted build must
not resume across the code change without the existing operator review process.

## Handcrafted quality reference

`examples/decision-desk/` implements the agent-action review problem with a paper,
forest and rust visual direction; queue and inspector; explicit scope/tool input;
required decision notes; immutable local reviews; search/filter/empty states and
JSON log export. Counts derive from five clearly labeled fictional requests.
Nothing executes a tool or sends email.

This is **handcrafted**, not an output of the changed generator or a model quality
benchmark. Adapt its product-thinking and interaction patterns to other problems;
do not copy its palette and layout into every product. Open `index.html` directly
in a modern browser, or serve that directory on loopback if file storage is restricted.

## Review an actual generated build

Save its full `BuildDossier` JSON locally. No model call is needed for review:

```sh
python tools/prototype-review/export_artifact.py build-dossier.json review-artifact
cd tools/prototype-review
npm ci --ignore-scripts --no-audit --no-fund
npx playwright install chromium
node review.mjs ../../review-artifact ../../review-evidence ../../my-scenarios.json
```

The exporter accepts only unique `index.html`, `styles.css` and `app.js` files,
refuses overwrites, preserves UTF-8 bytes, and records the same artifact digest
used by operator acceptance. It never publishes or accepts an artifact.

The reviewer serves immutable file snapshots on a temporary loopback port. Fresh
browser contexts contain no application credentials; external requests and service
workers are blocked. It never serves dossiers, environment files or reports, and
closes its browser and server afterward. It saves file hashes, desktop/tablet/mobile
screenshots, keyboard-focus evidence, overflow/error checks and supplied scenarios.
Compare file hashes with `artifact-manifest.json`. `BROWSER_CHANNEL=chrome` uses
installed Chrome; the default uses Playwright Chromium.

Scenario JSON uses accessible roles/labels with `click`, `fill`, `check`, `press`,
`reload`, `expectText`, `expectVisible`, `expectHidden`, `expectCount`, or
`downloadJson` and expected data fields. Arbitrary scripts and service credentials
are not inputs. See the reference's `scenarios.json`.

Review screenshots for readability, contrast, hierarchy, clear states and task flow.
Cover the approved acceptance criteria with behavioral scenarios. Passing this
baseline does not prove aesthetic quality, accessibility conformance, comprehensive
functional correctness, sandbox security or human acceptance. Network isolation
is a test boundary, not a production sandbox for hostile code. Use no sensitive data.

The new CI job exercises the reference and negative reviewer fixtures with no
providers and retains screenshots/reports. It has not run remotely until this
release is approved for source publication.

## Before claiming better model outputs

No paid generation benchmark was run. Compare old/new generators on the same
approved inputs, model/version and limits. Retain every artifact and failed attempt.
Use distinct tasks: agent-action review, an offline cost ledger and an evidence
comparison workspace. Independently test primary behavior, persistence, invalid
and empty cases at 390px and 1440px. Have a reviewer compare rendered candidates
without revealing their generator version; record preferences and reasons separately
from functional results and provider cost. These few cases cannot prove broad
generalization. The model's own design score is not a portfolio metric.

## Current hosting boundary

The live `protopro.vercel.app` website remains approved release `59c55f2`. These
new backend, tool and reference changes are local until separately approved for
publication. The existing Render API returned HTTP 503 during the website release.
No backend deployment, project-setting change, hosting upgrade, provider call,
master merge or generated-product publication is included in this work.
