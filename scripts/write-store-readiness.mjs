import { access, mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, resolve } from "node:path";

import sharp from "sharp";

const projectRoot = resolve(import.meta.dirname, "..");
const manifestPath = resolve(projectRoot, "assets/asset-manifest.json");
const captureValidationPath = resolve(
  projectRoot,
  "assets/reports/store-capture-validation.json",
);
const jsonReportPath = resolve(
  projectRoot,
  "assets/reports/store-asset-readiness.json",
);
const markdownReportPath = resolve(
  projectRoot,
  "docs/STORE_ASSET_READINESS.md",
);
const gate = process.argv.includes("--gate");

async function readJson(path, fallback = null) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") {
      return fallback;
    }
    throw error;
  }
}

function platformFor(assetId) {
  if (assetId.includes("google-play")) return "Google Play";
  if (assetId.includes("app-store-iphone")) return "App Store iPhone";
  if (assetId.includes("app-store-ipad")) return "App Store iPad";
  if (assetId.includes("open-graph")) return "Web / Open Graph";
  if (assetId.includes("discord")) return "Discord";
  return "Community / owned channels";
}

function markdown(value) {
  return String(value ?? "—")
    .replaceAll("|", "\\|")
    .replaceAll("\n", " ");
}

const [manifest, captureValidation] = await Promise.all([
  readJson(manifestPath),
  readJson(captureValidationPath),
]);
if (!manifest) {
  throw new Error("Asset manifest is missing.");
}
const assets = manifest.assets.filter(
  (asset) => asset.batch === "store-marketing",
);
if (assets.length !== 30) {
  throw new Error(
    `Store-marketing manifest must contain exactly 30 entries; found ${assets.length}.`,
  );
}
const captureById = new Map(
  (captureValidation?.captures ?? []).map((capture) => [
    capture.asset_id,
    capture,
  ]),
);
const findings = [];
const items = [];
for (const asset of assets) {
  const metadataPath = resolve(
    projectRoot,
    `assets/metadata/${asset.asset_id}.json`,
  );
  const metadata = await readJson(metadataPath);
  const capture = captureById.get(asset.asset_id);
  const file = capture?.file ?? metadata?.source_file ?? null;
  let actual = null;
  if (file) {
    const absolutePath = resolve(projectRoot, file);
    try {
      await access(absolutePath, constants.F_OK);
      const [image, fileStats] = await Promise.all([
        sharp(absolutePath).metadata(),
        stat(absolutePath),
      ]);
      actual = {
        width: image.width,
        height: image.height,
        format: image.format,
        channels: image.channels,
        has_alpha: image.hasAlpha,
        bytes: fileStats.size,
      };
      if (
        image.width !== asset.width ||
        image.height !== asset.height ||
        image.format !== "png"
      ) {
        findings.push(
          `${asset.asset_id}: ${image.width}x${image.height} ${image.format}; ` +
            `expected ${asset.width}x${asset.height} PNG`,
        );
      }
    } catch {
      findings.push(`${asset.asset_id}: source file is unreadable (${file})`);
    }
  } else {
    findings.push(`${asset.asset_id}: source file is missing`);
  }
  if (asset.status !== "approved") {
    findings.push(`${asset.asset_id}: status is ${asset.status}`);
  }
  if (
    asset.source_type === "app-screenshot" &&
    (!capture ||
      captureValidation?.status !== "passed" ||
      metadata?.source_type !== "app-screenshot" ||
      metadata?.provider !== "playwright-local-capture" ||
      metadata?.provenance?.source !== "functioning-local-application")
  ) {
    findings.push(
      `${asset.asset_id}: functioning-application capture provenance is incomplete`,
    );
  }
  if (
    asset.asset_id === "marketing-google-play-app-icon-v1" &&
    actual?.bytes > 1024 * 1024
  ) {
    findings.push(`${asset.asset_id}: Google Play icon exceeds 1 MiB`);
  }
  if (
    asset.asset_id === "marketing-google-play-feature-graphic-v1" &&
    actual?.has_alpha
  ) {
    findings.push(`${asset.asset_id}: Google Play feature graphic has alpha`);
  }
  items.push({
    asset_id: asset.asset_id,
    platform: platformFor(asset.asset_id),
    language: capture?.language ?? "language-neutral",
    route: capture?.route ?? null,
    width: asset.width,
    height: asset.height,
    format: "png",
    file,
    source:
      asset.source_type === "app-screenshot"
        ? "functioning-local-application"
        : (metadata?.source_type ?? asset.source_type),
    provider: metadata?.provider ?? null,
    status: asset.status,
    review_status: metadata?.review_status ?? null,
    sha256: metadata?.content_hash ?? null,
    actual,
  });
}

if (
  captureValidation?.status !== "passed" ||
  captureValidation?.capture_count !== 20
) {
  findings.push(
    "Real store capture validation is not passed for exactly 20 files",
  );
}
const report = {
  schema: "shadowgrid/store-asset-readiness/v1",
  generated_at: new Date().toISOString(),
  status: findings.length === 0 ? "passed" : "incomplete",
  manifest_entries: items.length,
  real_application_captures: captureValidation?.capture_count ?? 0,
  findings,
  items,
};
const table = items
  .map(
    (item) =>
      `| ${markdown(item.asset_id)} | ${markdown(item.platform)} | ` +
      `${item.width}×${item.height} PNG | ${markdown(item.language)} | ` +
      `${markdown(item.route)} | ${markdown(item.source)} | ${markdown(item.file)} | ` +
      `${markdown(item.status)} |`,
  )
  .join("\n");
const markdownReport = `# SHADOWGRID store asset readiness

Status: **${report.status}**

Generated: \`${report.generated_at}\`

The inventory contains exactly 30 required store, marketing and community entries. The
20 UI screenshots originate from the functioning seeded application; Playwright rejects
loading/error states, debug markers and exposed demo email addresses before capture.
Static artwork uses project-owned branding and visual-library sources. No generated or
mocked interface is accepted as an application screenshot.

## Inventory

| Asset | Platform | Dimensions | Language | Route | Source | File | Approval |
| --- | --- | --- | --- | --- | --- | --- | --- |
${table}

## Automated and visual evidence

- Capture validation: \`assets/reports/store-capture-validation.json\`
  (${captureValidation?.capture_count ?? 0} exact files, status
  \`${captureValidation?.status ?? "missing"}\`).
- Contact sheet: \`assets/reports/contact-sheets/store-captures-v1.png\`.
- Full-resolution representative review: iPhone exchange at 1290×2796 and iPad Germany
  map at 2048×2732; no loading, error, private identifier or debug overlay observed.
- Manifest and metadata gate: \`pnpm store:gate\`.
- Google Play constraints: 512×512 icon at no more than 1 MiB; 1024×500 opaque feature
  graphic; landscape screenshots at 2048×1152.
- Apple accepted source sizes used here: iPhone 1290×2796 and iPad 2048×2732.

Official references reviewed on 2026-07-30:

- [Google Play graphic asset requirements](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en)
- [Apple screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/)

## Language and external publication boundary

The canonical screenshot set is explicitly tagged \`en-US\`; non-screenshot brand art is
language-neutral. English and German store copy exists separately. A store operator may add
localized \`de-DE\` screenshot sets without replacing or relabelling these English sources.
Upload, store-console cropping, legal copy approval and localized experiment selection remain
external publication actions. They do not permit changing the evidence source or presenting
a generated UI as gameplay.

## Findings

${
  findings.length === 0
    ? "- None. All 30 entries passed file, dimension, provenance and approval gates."
    : findings.map((finding) => `- ${finding}`).join("\n")
}
`;
await Promise.all([
  mkdir(dirname(jsonReportPath), { recursive: true }),
  mkdir(dirname(markdownReportPath), { recursive: true }),
]);
await Promise.all([
  writeFile(jsonReportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8"),
  writeFile(markdownReportPath, `${markdownReport.trim()}\n`, "utf8"),
]);
if (gate && findings.length > 0) {
  throw new Error(
    `Store asset gate failed with ${findings.length} finding(s).`,
  );
}
process.stdout.write(
  `Store asset readiness ${report.status}: ${items.length} entries, ${findings.length} finding(s).\n`,
);
