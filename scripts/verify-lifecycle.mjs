import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDirectory, "..");
const plan = JSON.parse(
  readFileSync(resolve(scriptDirectory, "lifecycle-plan.json"), "utf8"),
);
const options = new Set(process.argv.slice(2));
const knownOptions = new Set(["--api-only", "--e2e-only", "--list"]);
const unknownOptions = [...options].filter((option) => !knownOptions.has(option));

if (unknownOptions.length > 0) {
  throw new Error(`Unknown lifecycle option(s): ${unknownOptions.join(", ")}`);
}
if (options.has("--api-only") && options.has("--e2e-only")) {
  throw new Error("--api-only and --e2e-only cannot be combined");
}

const unique = (values) => [...new Set(values)];
const apiTests = unique(plan.steps.flatMap((step) => step.api_tests));
const e2eSpecs = unique(plan.steps.flatMap((step) => step.e2e_specs));
const expectedNumbers = Array.from({ length: 30 }, (_, index) => index + 1);
const actualNumbers = plan.steps.map((step) => step.number);

if (JSON.stringify(actualNumbers) !== JSON.stringify(expectedNumbers)) {
  throw new Error("Lifecycle plan must contain ordered steps 1 through 30");
}
if (plan.personas.length !== 7) {
  throw new Error("Lifecycle plan must contain all seven required personas");
}

if (options.has("--list")) {
  console.log(
    JSON.stringify(
      {
        personas: plan.personas,
        steps: plan.steps.length,
        api_tests: apiTests,
        e2e_specs: e2eSpecs,
        browser_projects: ["chromium", "mobile"],
      },
      null,
      2,
    ),
  );
  process.exit(0);
}

const run = (command, args, label) => {
  console.log(`\n=== ${label} ===`);
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    env: process.env,
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
};

const pnpmRunner = process.env.npm_execpath
  ? [process.execPath, [process.env.npm_execpath]]
  : ["corepack", ["pnpm"]];

if (!options.has("--e2e-only")) {
  run(
    process.execPath,
    [
      "scripts/run-python.mjs",
      "--cwd",
      "apps/api",
      "-m",
      "pytest",
      "-q",
      ...apiTests,
    ],
    `API lifecycle (${apiTests.length} tests)`,
  );
}
if (!options.has("--api-only")) {
  run(
    pnpmRunner[0],
    [
      ...pnpmRunner[1],
      "--filter",
      "@shadowgrid/web",
      "exec",
      "playwright",
      "test",
      ...e2eSpecs,
    ],
    `Playwright lifecycle (${e2eSpecs.length} specs; desktop and mobile)`,
  );
}

console.log("\nSHADOWGRID lifecycle gate passed.");
