import { createReadStream } from "node:fs";
import { readdir, stat, writeFile } from "node:fs/promises";
import { createGzip } from "node:zlib";
import { dirname, extname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { pipeline } from "node:stream/promises";
import { Writable } from "node:stream";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDirectory, "../..");
const distRoot = resolve(projectRoot, "apps/web/dist");
const reportPath = resolve(
  projectRoot,
  "assets/reports/visual-performance-budget.json",
);

async function filesBelow(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map(async (entry) => {
      const path = resolve(directory, entry.name);
      return entry.isDirectory() ? filesBelow(path) : [path];
    }),
  );
  return nested.flat();
}

async function gzipSize(path) {
  let size = 0;
  await pipeline(
    createReadStream(path),
    createGzip({ level: 9 }),
    new Writable({
      write(chunk, _encoding, callback) {
        size += chunk.length;
        callback();
      },
    }),
  );
  return size;
}

const files = await filesBelow(distRoot);
const records = await Promise.all(
  files.map(async (path) => ({
    file: relative(projectRoot, path).replaceAll("\\", "/"),
    extension: extname(path),
    bytes: (await stat(path)).size,
    gzipBytes: [".js", ".css", ".html"].includes(extname(path))
      ? await gzipSize(path)
      : null,
  })),
);

const sumGzip = (extension) =>
  records
    .filter((record) => record.extension === extension)
    .reduce((total, record) => total + (record.gzipBytes ?? 0), 0);
const referenceImages = records.filter((record) =>
  /(?:global-landing|command-center|global-exchange-terminal).*1280\.(?:avif|webp)$/i.test(
    record.file,
  ),
);
const metrics = {
  javascriptGzipBytes: sumGzip(".js"),
  cssGzipBytes: sumGzip(".css"),
  htmlBytes: records
    .filter((record) => record.extension === ".html")
    .reduce((total, record) => total + record.bytes, 0),
  largestReferenceImageBytes: Math.max(
    0,
    ...referenceImages.map((record) => record.bytes),
  ),
};
const budgets = {
  javascriptGzipBytes: 460 * 1024,
  cssGzipBytes: 24 * 1024,
  htmlBytes: 6 * 1024,
  largestReferenceImageBytes: 400 * 1024,
};
const checks = Object.fromEntries(
  Object.entries(budgets).map(([name, budget]) => [
    name,
    {
      actual: metrics[name],
      budget,
      passed: metrics[name] <= budget,
    },
  ]),
);
const passed = Object.values(checks).every((check) => check.passed);

await writeFile(
  reportPath,
  `${JSON.stringify(
    {
      schemaVersion: 1,
      generatedAt: new Date().toISOString(),
      passed,
      checks,
      referenceImages,
      bundles: records.filter((record) =>
        [".js", ".css", ".html"].includes(record.extension),
      ),
    },
    null,
    2,
  )}\n`,
  "utf8",
);

for (const [name, check] of Object.entries(checks)) {
  console.log(
    `${check.passed ? "PASS" : "FAIL"} ${name}: ${check.actual} / ${check.budget} bytes`,
  );
}
if (!passed) process.exitCode = 1;
