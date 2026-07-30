import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { catalogBatches, catalogEntries } from "./catalog.mjs";
import { needsGeneration } from "./policy.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

test("manifest catalog has unique sequential order and ids", () => {
  assert.ok(catalogEntries.length > 800);
  assert.equal(
    new Set(catalogEntries.map((asset) => asset.asset_id)).size,
    catalogEntries.length,
  );
  assert.deepEqual(
    catalogEntries.map((asset) => asset.order),
    Array.from({ length: catalogEntries.length }, (_, index) => index + 1),
  );
});

test("all entries reference a declared batch and deterministic seed", () => {
  const batches = new Set(catalogBatches.map((batch) => batch.id));
  for (const asset of catalogEntries) {
    assert.ok(batches.has(asset.batch), asset.asset_id);
    assert.equal(asset.seed, 100000 + asset.order);
    assert.equal(asset.required, true);
  }
});

test("resume generation skips completed review items", () => {
  assert.equal(needsGeneration({ status: "pending" }), true);
  assert.equal(needsGeneration({ status: "failed" }), true);
  assert.equal(needsGeneration({ status: "approved" }), false);
  assert.equal(needsGeneration({ status: "review_required" }), false);
  assert.equal(needsGeneration({ status: "rejected" }), false);
});

test("store screenshots cannot be generated mock interfaces", () => {
  const screenshots = catalogEntries.filter(
    (asset) => asset.source_type === "app-screenshot",
  );
  assert.ok(screenshots.length >= 20);
  assert.ok(
    screenshots.every((asset) =>
      asset.notes.includes("generated or mock user interfaces are forbidden"),
    ),
  );
});

test("store catalog uses current exact icon, feature and screenshot dimensions", () => {
  const byId = new Map(catalogEntries.map((asset) => [asset.asset_id, asset]));
  assert.deepEqual(
    [
      "marketing-google-play-app-icon-v1",
      "marketing-google-play-feature-graphic-v1",
      "marketing-google-play-city-selection-v1",
      "marketing-app-store-iphone-1-v1",
      "marketing-app-store-ipad-1-v1",
      "marketing-open-graph-v1",
    ].map((assetId) => {
      const asset = byId.get(assetId);
      return [assetId, asset?.width, asset?.height];
    }),
    [
      ["marketing-google-play-app-icon-v1", 512, 512],
      ["marketing-google-play-feature-graphic-v1", 1024, 500],
      ["marketing-google-play-city-selection-v1", 2048, 1152],
      ["marketing-app-store-iphone-1-v1", 1290, 2796],
      ["marketing-app-store-ipad-1-v1", 2048, 2732],
      ["marketing-open-graph-v1", 1200, 630],
    ],
  );
});

test("geographic vectors require licensed source data", () => {
  const geography = catalogEntries.filter(
    (asset) => asset.source_type === "svg-geodata",
  );
  assert.equal(geography.length, 4);
  assert.ok(
    geography.every((asset) =>
      asset.notes.includes("licensed geographic source"),
    ),
  );
});

test("map markers are nineteen unique, self-contained runtime SVGs", () => {
  const markers = catalogEntries.filter(
    (asset) => asset.batch === "map-markers",
  );
  const hashes = new Set();

  assert.equal(markers.length, 19);
  for (const marker of markers) {
    const productionPath = resolve(
      root,
      "assets",
      "production",
      "svg",
      `${marker.asset_id}.svg`,
    );
    const runtimePath = resolve(
      root,
      "apps",
      "web",
      "public",
      "assets",
      "markers",
      `${marker.asset_id}.svg`,
    );
    const svg = readFileSync(productionPath, "utf8");

    assert.equal(readFileSync(runtimePath, "utf8"), svg, marker.asset_id);
    assert.match(svg, /width="24" height="24" viewBox="0 0 24 24"/);
    assert.match(svg, /<title id="title">/);
    assert.match(svg, /<desc id="description">/);
    assert.match(svg, /color="#[0-9a-f]{6}"/i);
    assert.doesNotMatch(svg, /<(?:script|image|text)\b/i);
    assert.doesNotMatch(svg, /\bhref\s*=/i);
    hashes.add(createHash("sha256").update(svg).digest("hex"));
  }
  assert.equal(hashes.size, markers.length);
});

test("interface icons remain visually distinct within each semantic family", () => {
  const families = [
    "navigation",
    "resource",
    "status",
    "pvp",
    "diplomacy",
    "building",
    "control",
  ];

  for (const family of families) {
    const icons = catalogEntries.filter((asset) =>
      asset.asset_id.startsWith(`icon-${family}-`),
    );
    const visualHashes = new Set(
      icons.map((icon) => {
        const svg = readFileSync(
          resolve(root, "assets", "production", "svg", `${icon.asset_id}.svg`),
          "utf8",
        )
          .replace(/<title[^>]*>[\s\S]*?<\/title>/, "")
          .replace(/<desc[^>]*>[\s\S]*?<\/desc>/, "")
          .replace(/\s+/g, " ");
        return createHash("sha256").update(svg).digest("hex");
      }),
    );

    assert.ok(icons.length > 0, family);
    assert.equal(visualHashes.size, icons.length, family);
  }
});

test("strategic state overlays use unique visual treatments", () => {
  const stateIds = [
    "overlay-economic-boom-v1",
    "overlay-crisis-v1",
    "overlay-authority-activity-v1",
    "overlay-organization-control-v1",
    "overlay-contested-district-v1",
    "overlay-blocked-territory-v1",
  ];
  const hashes = new Set(
    stateIds.map((assetId) => {
      const png = readFileSync(
        resolve(root, "assets", "production", "png", `${assetId}-1280.png`),
      );
      return createHash("sha256").update(png).digest("hex");
    }),
  );

  assert.equal(hashes.size, stateIds.length);
});
