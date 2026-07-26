import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { catalogBatches, catalogEntries } from "./catalog.mjs";

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
