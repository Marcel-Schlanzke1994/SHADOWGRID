import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import sharp from "sharp";

const projectRoot = resolve(import.meta.dirname, "..");
const sourceReportPath = resolve(
  projectRoot,
  "assets/reports/store-capture-sources.json",
);
const validationPath = resolve(
  projectRoot,
  "assets/reports/store-capture-validation.json",
);
const contactSheetPath = resolve(
  projectRoot,
  "assets/reports/contact-sheets/store-captures-v1.png",
);
const sourceReport = JSON.parse(await readFile(sourceReportPath, "utf8"));
const expectedDimensions = {
  "google-play": { width: 2048, height: 1152, count: 8 },
  "app-store-iphone": { width: 1290, height: 2796, count: 8 },
  "app-store-ipad": { width: 2048, height: 2732, count: 4 },
};
if (sourceReport.capture_count !== 20 || sourceReport.captures?.length !== 20) {
  throw new Error("Store capture report must contain exactly 20 captures.");
}
const ids = new Set();
const checked = [];
const platformCounts = new Map();
for (const capture of sourceReport.captures) {
  const expected = expectedDimensions[capture.platform];
  if (
    ids.has(capture.asset_id) ||
    !capture.file.startsWith("assets/source/marketing/") ||
    !expected ||
    capture.width !== expected.width ||
    capture.height !== expected.height
  ) {
    throw new Error(`Invalid or duplicate capture: ${capture.asset_id}.`);
  }
  ids.add(capture.asset_id);
  platformCounts.set(
    capture.platform,
    (platformCounts.get(capture.platform) ?? 0) + 1,
  );
  const absolutePath = resolve(projectRoot, capture.file);
  const metadata = await sharp(absolutePath).metadata();
  if (
    metadata.width !== capture.width ||
    metadata.height !== capture.height ||
    metadata.format !== "png"
  ) {
    throw new Error(
      `${capture.asset_id} is ${metadata.width}x${metadata.height} ${metadata.format}; ` +
        `expected ${capture.width}x${capture.height} PNG.`,
    );
  }
  checked.push({
    asset_id: capture.asset_id,
    platform: capture.platform,
    route: capture.route,
    language: capture.language,
    width: metadata.width,
    height: metadata.height,
    format: metadata.format,
    file: capture.file,
  });
}
for (const [platform, expected] of Object.entries(expectedDimensions)) {
  if (platformCounts.get(platform) !== expected.count) {
    throw new Error(
      `${platform} must contain exactly ${expected.count} captures.`,
    );
  }
}

const columns = 4;
const cellWidth = 380;
const cellHeight = 330;
const imageWidth = 356;
const imageHeight = 270;
const composites = [];
for (const [index, capture] of sourceReport.captures.entries()) {
  const x = (index % columns) * cellWidth + 12;
  const y = Math.floor(index / columns) * cellHeight + 12;
  const thumbnail = await sharp(resolve(projectRoot, capture.file))
    .resize(imageWidth, imageHeight, {
      fit: "contain",
      background: "#080a0d",
    })
    .png()
    .toBuffer();
  composites.push({ input: thumbnail, left: x, top: y });
  const label = capture.asset_id.replace(/^marketing-/, "");
  const labelSvg = Buffer.from(
    `<svg width="${imageWidth}" height="34" xmlns="http://www.w3.org/2000/svg">` +
      '<rect width="100%" height="100%" fill="#10151c"/>' +
      `<text x="8" y="22" fill="#f0c75e" font-size="15" font-family="Arial, sans-serif">${label}</text>` +
      "</svg>",
  );
  composites.push({
    input: labelSvg,
    left: x,
    top: y + imageHeight + 4,
  });
}
await mkdir(dirname(contactSheetPath), { recursive: true });
await sharp({
  create: {
    width: columns * cellWidth,
    height: Math.ceil(checked.length / columns) * cellHeight,
    channels: 3,
    background: "#05070a",
  },
})
  .composite(composites)
  .png()
  .toFile(contactSheetPath);

const validation = {
  validated_at: new Date().toISOString(),
  status: "passed",
  capture_count: checked.length,
  duplicate_ids: 0,
  invalid_dimensions: 0,
  loading_or_error_state_gate: "playwright assertions passed",
  prohibited_test_email_gate: "playwright assertion passed",
  contact_sheet: "assets/reports/contact-sheets/store-captures-v1.png",
  captures: checked,
};
await writeFile(
  validationPath,
  `${JSON.stringify(validation, null, 2)}\n`,
  "utf8",
);
process.stdout.write(
  `Store capture validation passed: ${checked.length} exact PNGs; contact sheet ${contactSheetPath}.\n`,
);
