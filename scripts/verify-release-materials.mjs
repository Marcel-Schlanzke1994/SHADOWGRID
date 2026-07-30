import { spawnSync } from "node:child_process";
import { access, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const projectRoot = resolve(import.meta.dirname, "..");
const ignoredDirectories = new Set([
  ".git",
  ".local",
  ".venv",
  "backups",
  "coverage",
  "dist",
  "node_modules",
  "playwright-report",
  "test-results",
]);
const externalSchemes = /^(?:https?:|mailto:|tel:|data:|app:)/i;

export function markdownLinkTargets(markdown) {
  const withoutCode = markdown
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`[^`\r\n]*`/g, "");
  const targets = [];
  const inline = /!?\[[^\]]*]\(\s*(<[^>]+>|[^)\s]+)(?:\s+["'][^)]*["'])?\s*\)/g;
  const references = /^\s*\[[^\]]+]:\s*(<[^>]+>|\S+)/gm;
  for (const expression of [inline, references]) {
    for (const match of withoutCode.matchAll(expression)) {
      targets.push(match[1].replace(/^<|>$/g, ""));
    }
  }
  return targets;
}

async function walkMarkdown(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.isDirectory() && ignoredDirectories.has(entry.name)) {
      continue;
    }
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walkMarkdown(path)));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) {
      files.push(path);
    }
  }
  return files;
}

function localTarget(sourceFile, rawTarget) {
  if (
    !rawTarget ||
    rawTarget.startsWith("#") ||
    rawTarget.startsWith("/") ||
    externalSchemes.test(rawTarget)
  ) {
    return null;
  }
  const pathPart = rawTarget.split("#", 1)[0].split("?", 1)[0];
  if (!pathPart) {
    return null;
  }
  try {
    return resolve(dirname(sourceFile), decodeURIComponent(pathPart));
  } catch {
    return resolve(dirname(sourceFile), pathPart);
  }
}

export async function checkDocumentationLinks(root = projectRoot) {
  const files = await walkMarkdown(root);
  const broken = [];
  let checkedLinks = 0;
  let externalLinks = 0;
  for (const file of files) {
    const markdown = await readFile(file, "utf8");
    for (const target of markdownLinkTargets(markdown)) {
      if (externalSchemes.test(target)) {
        externalLinks += 1;
        try {
          new URL(target);
        } catch {
          broken.push({
            source: relative(root, file),
            target,
            reason: "invalid_external_url",
          });
        }
        continue;
      }
      const path = localTarget(file, target);
      if (path === null) {
        continue;
      }
      checkedLinks += 1;
      try {
        await access(path, constants.F_OK);
      } catch {
        broken.push({
          source: relative(root, file),
          target,
          reason: "missing_local_target",
        });
      }
    }
  }
  return {
    markdown_files: files.length,
    checked_local_links: checkedLinks,
    syntactically_checked_external_links: externalLinks,
    broken,
  };
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
    windowsHide: true,
    ...options,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(
      `${command} ${args.join(" ")} failed with exit code ${result.status}: ${result.stderr.trim()}`,
    );
  }
  return result.stdout;
}

function isForbiddenLicense(license) {
  const normalized = license.toUpperCase();
  if (
    normalized.includes("AGPL") ||
    normalized.includes("SSPL") ||
    normalized.includes("BUSL") ||
    normalized.includes("BUSINESS SOURCE") ||
    normalized.includes("COMMONS CLAUSE") ||
    normalized.includes("UNLICENSED")
  ) {
    return true;
  }
  const hasPermissiveAlternative =
    normalized.includes(" OR ") &&
    /(MIT|BSD|APACHE|ISC|MPL|CC0|BLUEOAK|0BSD)/.test(normalized);
  return /(?:^|[^A-Z])GPL(?:-|$)/.test(normalized) && !hasPermissiveAlternative;
}

function pythonExecutable() {
  return process.platform === "win32"
    ? resolve(projectRoot, ".venv/Scripts/python.exe")
    : resolve(projectRoot, ".venv/bin/python");
}

export function scanDependencyLicenses() {
  const pnpmCommand = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
  const nodeLicenses = JSON.parse(
    run(pnpmCommand, ["licenses", "list", "--json", "--prod"], {
      shell: process.platform === "win32",
    }),
  );
  const pythonProgram = [
    "import importlib.metadata as metadata",
    "import json",
    "rows = []",
    "for distribution in metadata.distributions():",
    "    name = distribution.metadata.get('Name') or distribution.metadata.get('Summary') or 'unknown'",
    "    expression = distribution.metadata.get('License-Expression')",
    "    declared = expression or distribution.metadata.get('License') or ''",
    "    if not declared:",
    "        classifiers = distribution.metadata.get_all('Classifier') or []",
    "        declared = ' OR '.join(item.split(' :: ')[-1] for item in classifiers if item.startswith('License ::'))",
    "    rows.append({'name': name, 'version': distribution.version, 'license': declared or 'UNKNOWN'})",
    "print(json.dumps(sorted(rows, key=lambda row: row['name'].lower())))",
  ].join("\n");
  const pythonLicenses = JSON.parse(
    run(pythonExecutable(), ["-c", pythonProgram]),
  );
  const nodeSummary = Object.fromEntries(
    Object.entries(nodeLicenses).map(([license, packages]) => [
      license,
      packages.length,
    ]),
  );
  const forbidden = [
    ...Object.entries(nodeLicenses)
      .filter(([license]) => isForbiddenLicense(license))
      .flatMap(([license, packages]) =>
        packages.map((entry) => ({
          ecosystem: "node",
          name: entry.name,
          version: entry.versions.join(","),
          license,
        })),
      ),
    ...pythonLicenses
      .filter((entry) => isForbiddenLicense(entry.license))
      .map((entry) => ({ ecosystem: "python", ...entry })),
  ];
  return {
    node: {
      license_families: nodeSummary,
      package_records: Object.values(nodeLicenses).reduce(
        (total, packages) => total + packages.length,
        0,
      ),
    },
    python: {
      package_records: pythonLicenses.length,
      unknown_license_records: pythonLicenses
        .filter((entry) => entry.license === "UNKNOWN")
        .map((entry) => `${entry.name}@${entry.version}`),
      reviewed_weak_copyleft_records: pythonLicenses
        .filter((entry) => /(?:^|[^A-Z])(LGPL|MPL)(?:-|$)/i.test(entry.license))
        .map((entry) => `${entry.name}@${entry.version}:${entry.license}`),
    },
    forbidden,
  };
}

async function main() {
  const [documentation, licenses] = await Promise.all([
    checkDocumentationLinks(),
    Promise.resolve().then(() => scanDependencyLicenses()),
  ]);
  const report = {
    schema: "shadowgrid/release-materials-scan/v1",
    checked_at: new Date().toISOString(),
    documentation,
    licenses,
    status:
      documentation.broken.length === 0 && licenses.forbidden.length === 0
        ? "passed"
        : "failed",
  };
  const reportPath = resolve(
    projectRoot,
    ".project/release-materials-scan.json",
  );
  await mkdir(dirname(reportPath), { recursive: true });
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  if (report.status !== "passed") {
    process.stderr.write(`${JSON.stringify(report, null, 2)}\n`);
    process.exitCode = 1;
    return;
  }
  process.stdout.write(
    `Release materials passed: ${documentation.markdown_files} Markdown files, ` +
      `${documentation.checked_local_links} local links, ` +
      `${licenses.node.package_records} Node and ${licenses.python.package_records} Python package records.\n`,
  );
}

const invokedPath = process.argv[1]
  ? pathToFileURL(resolve(process.argv[1])).href
  : "";
if (import.meta.url === invokedPath) {
  await main();
}
