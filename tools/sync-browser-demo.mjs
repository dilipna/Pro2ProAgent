import { readFile, writeFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const check = process.argv.includes("--check");
for (const name of ["index.html", "styles.css", "app.js"]) {
  let source = await readFile(
    resolve(root, "examples/decision-desk", name),
    "utf8",
  );
  // Canonicalize checkout line endings so Windows/Linux produce identical assets.
  source = source.replace(/\r\n/g, "\n");
  if (name === "index.html")
    source = source
      .replace(
        'class="brand" href="./"',
        'class="brand" href="/prototypes" aria-label="Back to ProToPro prototype notes"',
      )
      .replace(
        "No tools or external services connected.</small>",
        'No tools or external services connected.</small><a class="back-to-product" href="/prototypes">← Back to ProToPro</a>',
      );
  if (name === "styles.css")
    source +=
      "\n.back-to-product{display:block;margin-top:20px;color:#f0ece1;text-underline-offset:4px}.back-to-product:focus-visible{outline:2px solid #f0ece1;outline-offset:5px}\n";
  const dest = resolve(root, "web/public/demos/decision-desk", name);
  if (check) {
    if ((await readFile(dest, "utf8")).replace(/\r\n/g, "\n") !== source)
      throw new Error(
        `Public demo drift: ${name}. Run node tools/sync-browser-demo.mjs`,
      );
  } else {
    await mkdir(dirname(dest), { recursive: true });
    await writeFile(dest, source);
  }
}
console.log(
  check
    ? "Public demo matches canonical reference."
    : "Public demo synchronized.",
);
