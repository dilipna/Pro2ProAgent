/** Exercise the actual production Next.js build; never a cloud API or model. */
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { chromium } from "playwright";
import { perform } from "./review.mjs";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const output = resolve(
  process.argv[2] || join(root, "test-evidence/browser-edition"),
);
await mkdir(output, { recursive: true });
const port = Number(process.env.QA_PORT || 3201),
  base = `http://127.0.0.1:${port}`;
const report = { status: "FAIL", checks: [], errors: [], upstreamRequests: [] };
const trap = createServer((req, res) => {
  report.upstreamRequests.push({ method: req.method, path: req.url });
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(
    JSON.stringify({
      model_configured: false,
      outcome: "unavailable",
      run_id: null,
      matches: [],
    }),
  );
});
await new Promise((done) => trap.listen(0, "127.0.0.1", done));
const upstream = `http://127.0.0.1:${trap.address().port}`;
const children = [];
let browser;
async function start(serverPort, mode) {
  const child = spawn(
    process.execPath,
    [
      "node_modules/next/dist/bin/next",
      "start",
      "-H",
      "127.0.0.1",
      "-p",
      String(serverPort),
    ],
    {
      cwd: join(root, "web"),
      env: {
        ...process.env,
        PROTOPRO_BACKEND_MODE: mode,
        PROTOPRO_API_URL: upstream,
        NEXT_TELEMETRY_DISABLED: "1",
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  children.push(child);
  let logs = "";
  child.stdout.on("data", (b) => {
    logs = (logs + b).slice(-10000);
  });
  child.stderr.on("data", (b) => {
    logs = (logs + b).slice(-10000);
  });
  for (let attempt = 0; attempt < 90; attempt++) {
    if (child.exitCode !== null) throw new Error(`Next server exited: ${logs}`);
    try {
      const res = await fetch(`http://127.0.0.1:${serverPort}/prototypes`);
      if (res.status === 200) return;
    } catch {}
    await new Promise((done) => setTimeout(done, 500));
  }
  throw new Error(`Next server did not start: ${logs}`);
}
try {
  await start(port, "browser");
  for (const [method, path] of [
    ["POST", "/api/search"],
    ["GET", "/api/search/runs/example"],
    ["GET", "/api/console/reviews"],
    ["POST", "/api/console/reviews/example"],
    ["GET", "/api/console/runs/example/stream"],
    ["GET", "/api/workspace/workspace/config"],
    ["POST", "/api/workspace/briefs/import"],
    ["POST", "/api/workspace/reviews/example"],
    ["POST", "/api/workspace/briefs/" + "a".repeat(32) + "/execute"],
  ]) {
    const response = await fetch(base + path, {
      method,
      ...(method === "POST" ? { body: "malformed input" } : {}),
    });
    assert.equal(response.status, 503, path);
    assert.equal((await response.json()).mode, "browser");
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
  report.checks.push(
    "Nine public read/mutation probes fail closed before parsing or upstream access.",
  );
  browser = await chromium.launch({
    ...(process.env.BROWSER_CHANNEL
      ? { channel: process.env.BROWSER_CHANNEL }
      : {}),
    headless: true,
  });
  for (const width of [1440, 768, 390]) {
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => report.errors.push(e.message));
    page.on("console", (message) => {
      if (message.type() === "error") report.errors.push(message.text());
    });
    for (const path of [
      "/",
      "/prototypes",
      "/demos/decision-desk/index.html",
      "/engineering",
      "/console",
      "/workspace",
    ]) {
      const response = await page.goto(base + path, {
        waitUntil: "networkidle",
      });
      assert.equal(response.status(), 200, path);
      assert.equal(await page.locator("h1").count(), 1, path);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth + 1,
        ),
        false,
        `${path} overflow at ${width}`,
      );
      if (path === "/demos/decision-desk/index.html") {
        assert.match(
          response.headers()["content-security-policy"],
          /connect-src 'none'/,
        );
        await page.screenshot({
          path: join(output, `decision-desk-${width}.png`),
          fullPage: true,
        });
      }
      if (path === "/prototypes")
        await page.screenshot({
          path: join(output, `prototypes-${width}.png`),
          fullPage: true,
        });
      if (path === "/")
        await page.screenshot({
          path: join(output, `home-${width}.png`),
          fullPage: true,
        });
      if (path === "/console" || path === "/workspace")
        assert.equal(
          await page.locator("input[type=password]").count(),
          0,
          "public pages must not collect operator keys",
        );
    }
    await page.goto(base, { waitUntil: "networkidle" });
    await page
      .getByLabel("Search recorded problems")
      .fill("no-record-will-match-this");
    await page
      .getByRole("heading", { name: "No recorded problems match." })
      .waitFor();
    await page.getByRole("button", { name: "Clear library search" }).click();
    assert.ok(
      (await page.getByLabel("Search recorded problems").inputValue()) === "",
    );
    await page.getByRole("link", { name: "Try a working prototype" }).click();
    await page
      .getByRole("link", { name: "Open Decision Desk ↗", exact: true })
      .click();
    await page
      .getByRole("link", { name: "← Back to ProToPro", exact: true })
      .click();
    await page
      .getByRole("heading", {
        name: "A small product. A complete interaction.",
      })
      .waitFor();
    report.checks.push(
      `Six routes, no overflow, recorded search and demo return navigation at ${width}px.`,
    );
    await context.close();
  }
  const scenarios = JSON.parse(
    await readFile(join(root, "examples/decision-desk/scenarios.json"), "utf8"),
  );
  for (const scenario of scenarios) {
    const context = await browser.newContext({
      viewport: { width: scenario.width, height: 1000 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => report.errors.push(e.message));
    page.on("console", (message) => {
      if (message.type() === "error") report.errors.push(message.text());
    });
    await page.goto(base + "/demos/decision-desk/index.html", {
      waitUntil: "networkidle",
    });
    await perform(page, scenario.steps);
    report.checks.push(`Hosted demo scenario: ${scenario.name}`);
    await context.close();
  }
  const context = await browser.newContext({
    viewport: { width: 390, height: 1000 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  await page.goto(base + "/demos/decision-desk/index.html", {
    waitUntil: "networkidle",
  });
  await page.keyboard.press("Tab");
  assert.equal(
    await page.locator(":focus").textContent(),
    "Skip to review queue",
  );
  await page.keyboard.press("Enter");
  // The policy must block even same-origin network calls from the static demo.
  assert.equal(
    await page.evaluate(async () => {
      try {
        await fetch("/api/search", { method: "POST", body: "{}" });
        return false;
      } catch {
        return true;
      }
    }),
    true,
  );
  await page.goto(base + "/discover", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Load recorded example" }).click();
  await page
    .getByLabel("What should this prototype accomplish?")
    .fill("Preserve evidence and a bounded review log");
  await page.getByRole("button", { name: "Continue to scope review" }).click();
  await page.getByRole("button", { name: "Open draft from discovery" }).click();
  await page
    .getByText("Preserve evidence and a bounded review log", { exact: true })
    .waitFor();
  await page
    .getByRole("heading", { name: "Review here. Build locally." })
    .waitFor();
  report.checks.push(
    "Keyboard skip link, same-origin CSP network rejection and edited discovery handoff passed.",
  );
  await context.close();
  assert.equal(
    report.upstreamRequests.length,
    0,
    "browser edition must never contact configured upstream",
  );
  report.checks.push(
    "Configured upstream trap received zero browser-edition requests.",
  );
  await start(port + 1, "connected");
  const response = await fetch(
    `http://127.0.0.1:${port + 1}/api/workspace/workspace/config`,
  );
  assert.equal(response.status, 200);
  assert.equal((await response.json()).model_configured, false);
  assert.deepEqual(report.upstreamRequests, [
    { method: "GET", path: "/api/v1/workspace/config" },
  ]);
  const local = await browser.newPage();
  await local.goto(`http://127.0.0.1:${port + 1}/workspace`, {
    waitUntil: "networkidle",
  });
  await local.getByLabel("Operator key", { exact: true }).waitFor();
  await local.close();
  report.checks.push(
    "Explicit connected mode forwards to a local stub and restores the operator form. No real backend/model contacted.",
  );
  assert.deepEqual(report.errors, []);
  report.status = "PASS";
} catch (error) {
  report.failure = String(error);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  for (const child of children) {
    child.kill();
    await new Promise((done) => {
      if (child.exitCode !== null) return done();
      child.once("exit", done);
      setTimeout(done, 3000);
    });
  }
  await new Promise((done) => trap.close(done));
  await writeFile(
    join(output, "browser-edition.json"),
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
}
