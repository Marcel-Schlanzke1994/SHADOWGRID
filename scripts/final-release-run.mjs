import { createHash } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import {
  appendFile,
  mkdir,
  readFile,
  readdir,
  stat,
  writeFile,
} from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const startedAt = new Date();
const compactTime = startedAt
  .toISOString()
  .replaceAll(/[-:]/g, "")
  .replace(/\.\d{3}Z$/, "Z");
const runId = `final-release-${compactTime}`;
const evidenceRoot = resolve(projectRoot, "docs/release-evidence", runId);
const logRoot = resolve(evidenceRoot, "logs");
const reportPath = resolve(evidenceRoot, "FINAL_RELEASE_RUN.json");
const databaseRelative = `.local/${runId}.sqlite3`;
const databaseAbsolute = resolve(projectRoot, databaseRelative);
const pythonPath =
  process.platform === "win32"
    ? resolve(projectRoot, ".venv/Scripts/python.exe")
    : resolve(projectRoot, ".venv/bin/python");
const releaseEnvironment = {
  ...process.env,
  APP_ENV: "local",
  DATABASE_URL: `sqlite:///${databaseAbsolute.replaceAll("\\", "/")}`,
  FORCE_COLOR: "0",
  NO_COLOR: "1",
  SHADOWGRID_FINAL_RUN_ID: runId,
};

function capture(command, args) {
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    encoding: "utf8",
    env: releaseEnvironment,
    windowsHide: true,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(
      `${command} ${args.join(" ")} failed with exit code ${result.status}: ${result.stderr.trim()}`,
    );
  }
  return result.stdout.trim();
}

const pnpmRunner = process.env.npm_execpath
  ? { command: process.execPath, prefix: [process.env.npm_execpath] }
  : { command: "corepack", prefix: ["pnpm"] };
const pnpm = (...args) => ({
  command: pnpmRunner.command,
  args: [...pnpmRunner.prefix, ...args],
  display: `pnpm ${args.join(" ")}`,
});
const git = (...args) => capture("git", args);

const dirty = git("status", "--porcelain", "--untracked-files=all");
if (dirty) {
  process.stderr.write(
    "Final release run requires a clean candidate commit. Commit the reviewed source and evidence inputs first.\n",
  );
  process.exit(2);
}

await mkdir(logRoot, { recursive: true });
await mkdir(dirname(databaseAbsolute), { recursive: true });

const report = {
  schema: "shadowgrid/final-release-run/v1",
  run_id: runId,
  status: "running",
  candidate_commit: git("rev-parse", "HEAD"),
  branch: git("branch", "--show-current"),
  started_at: startedAt.toISOString(),
  finished_at: null,
  database: databaseRelative,
  clean_candidate_worktree: true,
  tool_versions: {
    git: git("--version"),
    node: process.version,
    pnpm: capture(pnpmRunner.command, [...pnpmRunner.prefix, "--version"]),
    python: capture(pythonPath, ["--version"]),
    playwright: capture(pnpmRunner.command, [
      ...pnpmRunner.prefix,
      "--filter",
      "@shadowgrid/web",
      "exec",
      "playwright",
      "--version",
    ]),
  },
  steps: [],
  summaries: {},
  external_gates: [],
};

async function persistReport() {
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

function safeName(value) {
  return value
    .toLowerCase()
    .replaceAll(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

async function runStep(index, name, invocation) {
  const logPath = resolve(
    logRoot,
    `${String(index).padStart(2, "0")}-${safeName(name)}.log`,
  );
  const started = new Date();
  const step = {
    index,
    name,
    command: invocation.display,
    started_at: started.toISOString(),
    finished_at: null,
    duration_seconds: null,
    exit_code: null,
    log: relative(projectRoot, logPath).replaceAll("\\", "/"),
    log_sha256: null,
  };
  report.steps.push(step);
  await writeFile(
    logPath,
    `SHADOWGRID final release evidence\nStep: ${name}\nCommand: ${invocation.display}\nStarted: ${step.started_at}\n\n`,
    "utf8",
  );
  await persistReport();
  process.stdout.write(`\n=== ${index}. ${name} ===\n${invocation.display}\n`);
  let writeChain = Promise.resolve();
  const exitCode = await new Promise((resolveExit, reject) => {
    const child = spawn(invocation.command, invocation.args, {
      cwd: projectRoot,
      env: releaseEnvironment,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    child.on("error", reject);
    for (const stream of [child.stdout, child.stderr]) {
      stream.on("data", (chunk) => {
        process.stdout.write(chunk);
        writeChain = writeChain.then(() => appendFile(logPath, chunk));
      });
    }
    child.on("close", (code) => resolveExit(code ?? 1));
  });
  await writeChain;
  const finished = new Date();
  await appendFile(
    logPath,
    `\nFinished: ${finished.toISOString()}\nExit code: ${exitCode}\n`,
  );
  const logBytes = await readFile(logPath);
  step.finished_at = finished.toISOString();
  step.duration_seconds = Number(
    ((finished.getTime() - started.getTime()) / 1000).toFixed(3),
  );
  step.exit_code = exitCode;
  step.log_sha256 = createHash("sha256").update(logBytes).digest("hex");
  if (exitCode !== 0) {
    report.status = "failed";
    report.finished_at = finished.toISOString();
  }
  await persistReport();
  if (exitCode !== 0) {
    throw new Error(`${name} failed with exit code ${exitCode}.`);
  }
}

const steps = [
  ["Clean reproducible build outputs", pnpm("clean")],
  ["Install lockfile dependencies", pnpm("install", "--frozen-lockfile")],
  [
    "Install pinned Python dependencies",
    {
      command: pythonPath,
      args: [
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        "apps/api/requirements-dev.txt",
      ],
      display:
        "python -m pip install --disable-pip-version-check -r apps/api/requirements-dev.txt",
    },
  ],
  ["Migrate fresh release database", pnpm("migrate")],
  ["Seed fresh release database first pass", pnpm("seed")],
  ["Seed fresh release database idempotency pass", pnpm("seed")],
  ["Verify fresh data invariants", pnpm("data:verify")],
  ["Run complete validation gate", pnpm("validate")],
  ["Run asset pipeline unit tests", pnpm("assets:test")],
  ["Validate asset files and metadata", pnpm("assets:validate")],
  ["Verify asset runtime integration", pnpm("assets:integration-test")],
  ["Enforce complete asset release gate", pnpm("assets:gate")],
  ["Run deterministic balance simulation", pnpm("test:balance")],
  ["Run backup and isolated restore drill", pnpm("ops:restore-drill")],
  ["Verify data invariants after restore drill", pnpm("data:verify")],
  ["Run full multi-persona lifecycle gate", pnpm("test:lifecycle")],
  ["Build web production bundle", pnpm("--filter", "@shadowgrid/web", "build")],
  [
    "Build unsigned all-platform mobile preview",
    pnpm("--filter", "@shadowgrid/mobile", "build:preview"),
  ],
  ["Run security and dependency audit", pnpm("test:security")],
  [
    "Run complete accessibility matrix",
    pnpm(
      "--filter",
      "@shadowgrid/web",
      "exec",
      "playwright",
      "test",
      "e2e/accessibility-matrix.spec.ts",
    ),
  ],
  [
    "Check documentation links and dependency licenses",
    pnpm("release:materials"),
  ],
  ["Run independent secret scan", pnpm("scan:secrets")],
  ["Validate exact real store captures", pnpm("store:validate-captures")],
  ["Enforce complete store and marketing asset gate", pnpm("store:gate")],
  ["Verify mobile release configuration", pnpm("mobile:release:verify")],
  ["Verify operations configuration", pnpm("ops:verify")],
];

try {
  for (const [offset, [name, invocation]] of steps.entries()) {
    await runStep(offset + 1, name, invocation);
  }
} catch (error) {
  process.stderr.write(
    `${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exit(1);
}

async function directoryStats(path) {
  const result = { files: 0, bytes: 0 };
  try {
    for (const entry of await readdir(path, { withFileTypes: true })) {
      const child = resolve(path, entry.name);
      if (entry.isDirectory()) {
        const nested = await directoryStats(child);
        result.files += nested.files;
        result.bytes += nested.bytes;
      } else if (entry.isFile()) {
        result.files += 1;
        result.bytes += (await stat(child)).size;
      }
    }
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }
  return result;
}

async function readJsonIfPresent(path) {
  try {
    return JSON.parse(await readFile(resolve(projectRoot, path), "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") {
      return null;
    }
    throw error;
  }
}

const allLogs = (
  await Promise.all(
    report.steps.map((step) =>
      readFile(resolve(projectRoot, step.log), "utf8"),
    ),
  )
).join("\n");
const summaryLines = [
  ...new Set(
    allLogs
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) =>
        /(?:\d+ passed|TOTAL\s+\d+|coverage|Asset release gate passed|load|Exported:|built in)/i.test(
          line,
        ),
      ),
  ),
];
const [assetState, balance, restore, store, materials, finalization] =
  await Promise.all([
    readJsonIfPresent(".project/asset-generation-state.json"),
    readJsonIfPresent(".project/balance-simulation-results.json"),
    readJsonIfPresent(".project/restore-drill-result.json"),
    readJsonIfPresent("assets/reports/store-capture-validation.json"),
    readJsonIfPresent(".project/release-materials-scan.json"),
    readJsonIfPresent(".project/finalization-state.json"),
  ]);
report.status = "passed";
report.finished_at = new Date().toISOString();
report.summaries = {
  observed_test_and_build_lines: summaryLines,
  builds: {
    web: await directoryStats(resolve(projectRoot, "apps/web/dist")),
    mobile_preview: await directoryStats(
      resolve(projectRoot, "apps/mobile/dist/preview"),
    ),
  },
  assets: assetState,
  balance,
  backup_restore: restore,
  store_captures: store,
  release_materials: materials,
};
report.external_gates = finalization?.external_gates ?? [];
await persistReport();
process.stdout.write(
  `\nFinal release run passed. Evidence: ${relative(projectRoot, reportPath)}\n`,
);
