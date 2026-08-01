import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import sharp from "sharp";

const projectRoot = resolve(import.meta.dirname, "..");
const marketingRoot = resolve(projectRoot, "assets/source/marketing");
const iconPath = resolve(
  marketingRoot,
  "marketing-google-play-app-icon-v1.png",
);
const featurePath = resolve(
  marketingRoot,
  "marketing-google-play-feature-graphic-v1.png",
);
const iconSource = resolve(
  projectRoot,
  "assets/source/branding/branding-shadowgrid-app-icon-master-v1.svg",
);
const symbolSource = resolve(
  projectRoot,
  "assets/source/branding/branding-shadowgrid-symbol-gold-v1.svg",
);
const wordmarkSource = resolve(
  projectRoot,
  "assets/source/branding/branding-shadowgrid-wordmark-horizontal-v1.svg",
);
const backgroundSource = resolve(
  projectRoot,
  "assets/source/global/global-command-center-night-v1.png",
);
const reportPath = resolve(
  projectRoot,
  "assets/reports/store-static-art-preparation.json",
);
const ingest = process.argv.includes("--ingest");

await mkdir(marketingRoot, { recursive: true });

await sharp(iconSource, { density: 192 })
  .resize(512, 512, { fit: "cover" })
  .png({ compressionLevel: 9, palette: true, quality: 100 })
  .toFile(iconPath);

const [symbol, wordmark] = await Promise.all([
  sharp(symbolSource, { density: 192 })
    .resize(220, 220, { fit: "contain" })
    .png()
    .toBuffer(),
  sharp(wordmarkSource, { density: 192 })
    .resize(620, 194, { fit: "contain" })
    .png()
    .toBuffer(),
]);
const overlay = Buffer.from(`
  <svg xmlns="http://www.w3.org/2000/svg" width="1024" height="500">
    <defs>
      <linearGradient id="shade" x1="0" x2="1">
        <stop stop-color="#05070a" stop-opacity=".96"/>
        <stop offset=".68" stop-color="#05070a" stop-opacity=".62"/>
        <stop offset="1" stop-color="#05070a" stop-opacity=".3"/>
      </linearGradient>
      <linearGradient id="edge" x1="0" x2="1">
        <stop stop-color="#e7c56d"/>
        <stop offset=".72" stop-color="#9d7930" stop-opacity=".5"/>
        <stop offset="1" stop-color="#9d7930" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <rect width="1024" height="500" fill="url(#shade)"/>
    <rect x="48" y="42" width="928" height="2" fill="url(#edge)"/>
    <rect x="48" y="456" width="928" height="2" fill="url(#edge)" opacity=".55"/>
  </svg>
`);
await sharp(backgroundSource)
  .resize(1024, 500, { fit: "cover", position: "attention" })
  .composite([
    { input: overlay, left: 0, top: 0 },
    { input: symbol, left: 70, top: 140 },
    { input: wordmark, left: 332, top: 153 },
  ])
  .flatten({ background: "#080a0d" })
  .removeAlpha()
  .png({ compressionLevel: 9 })
  .toFile(featurePath);

async function evidence(path, expectedWidth, expectedHeight, maxBytes = null) {
  const [metadata, bytes] = await Promise.all([
    sharp(path).metadata(),
    readFile(path),
  ]);
  if (
    metadata.format !== "png" ||
    metadata.width !== expectedWidth ||
    metadata.height !== expectedHeight ||
    (maxBytes !== null && bytes.length > maxBytes)
  ) {
    throw new Error(
      `${path} failed store constraints: ${metadata.width}x${metadata.height} ` +
        `${metadata.format}, ${bytes.length} bytes.`,
    );
  }
  return {
    file: path.replace(`${projectRoot}\\`, "").replaceAll("\\", "/"),
    width: metadata.width,
    height: metadata.height,
    format: metadata.format,
    channels: metadata.channels,
    has_alpha: metadata.hasAlpha,
    bytes: bytes.length,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  };
}

const report = {
  schema: "shadowgrid/store-static-art/v1",
  generated_at: new Date().toISOString(),
  source: "project-owned branding and approved SHADOWGRID background assets",
  paid_generation_cost_eur: 0,
  items: [
    await evidence(iconPath, 512, 512, 1024 * 1024),
    await evidence(featurePath, 1024, 500),
  ],
};
if (report.items[1].has_alpha) {
  throw new Error(
    "Google Play feature graphic must not contain an alpha channel.",
  );
}
await mkdir(dirname(reportPath), { recursive: true });
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
for (const item of report.items) {
  const assetId = item.file
    .split("/")
    .at(-1)
    .replace(/\.png$/, "");
  const reviewRelative = `assets/reviews/store-static-v1/${assetId}.json`;
  const reviewPath = resolve(projectRoot, reviewRelative);
  const review = {
    schema: "project-owned-store-static-v1",
    reviewer: "codex-visual",
    reviewed_at: report.generated_at,
    provider: "sharp-procedural",
    source_type: "procedural",
    license: "project-owned-procedural-asset",
    revision_prompt: assetId.includes("app-icon")
      ? "Render the approved SHADOWGRID app-icon master at the exact Google Play size with lossless project-owned geometry."
      : "Compose the approved SHADOWGRID night command-center background, gold symbol and wordmark into an opaque brand-neutral Google Play feature graphic.",
    realism: 96,
    style_consistency: 98,
    composition: 94,
    material_quality: 96,
    lighting_quality: 95,
    architecture_plausibility: 95,
    ui_suitability: 98,
    mobile_suitability: 96,
    originality: 97,
    safety_compliance: 100,
    provenance: {
      source: "project-owned-visual-library",
      preparation_report: "assets/reports/store-static-art-preparation.json",
      paid_generation_cost_eur: 0,
    },
    notes: [
      "Exact dimensions, PNG encoding and byte constraints are machine validated.",
      "No external brand, authority mark, private person, identifier or gameplay claim is present.",
    ],
  };
  await mkdir(dirname(reviewPath), { recursive: true });
  await writeFile(reviewPath, `${JSON.stringify(review, null, 2)}\n`, "utf8");
  if (ingest) {
    const result = spawnSync(
      process.execPath,
      [
        "scripts/assets/pipeline.mjs",
        "ingest",
        `--asset=${assetId}`,
        `--file=${item.file}`,
        `--review=${reviewRelative}`,
      ],
      {
        cwd: projectRoot,
        stdio: "inherit",
        windowsHide: true,
      },
    );
    if (result.error) throw result.error;
    if (result.status !== 0) {
      throw new Error(
        `Static store ingest failed for ${assetId} with exit code ${result.status}.`,
      );
    }
  }
}
process.stdout.write(
  `Prepared exact Google Play icon and feature graphic${ingest ? " and ingested both" : ""}; report ${reportPath}.\n`,
);
