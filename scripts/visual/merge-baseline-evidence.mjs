import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDirectory, "../..");
const reportRoot = resolve(projectRoot, "assets/reports");
const reports = await Promise.all(
  ["desktop", "mobile"].map(async (viewport) =>
    JSON.parse(
      await readFile(
        resolve(reportRoot, `visual-baseline-captures-${viewport}.json`),
        "utf8",
      ),
    ),
  ),
);
const captures = reports.flatMap((report) => report.captures);
if (captures.length !== 74) {
  throw new Error(`Expected 74 baseline captures, found ${captures.length}.`);
}
await writeFile(
  resolve(reportRoot, "visual-baseline-captures.json"),
  `${JSON.stringify(
    {
      schema_version: 1,
      source: "functioning-local-application",
      seeded_account: "advanced-demo-persona",
      captures,
    },
    null,
    2,
  )}\n`,
  "utf8",
);
console.log(`Merged ${captures.length} visual baseline captures.`);
