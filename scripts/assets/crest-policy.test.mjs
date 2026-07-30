import assert from "node:assert/strict";
import test from "node:test";
import {
  buildCrestCombinationDescriptors,
  validateCrestCombinations,
} from "./crest-policy.mjs";

test("crest configurator defines 100 unique deterministic combinations", () => {
  const descriptors = buildCrestCombinationDescriptors();
  const validation = validateCrestCombinations(descriptors);

  assert.equal(descriptors.length, 100);
  assert.equal(validation.unique_signature_count, 100);
  assert.equal(validation.duplicate_signatures, 0);
  assert.equal(validation.problematic_symbol_count, 0);
  assert.equal(validation.passed, true);
});

test("crest combinations preserve accessible foreground contrast", () => {
  const validation = validateCrestCombinations();

  assert.ok(validation.minimum_contrast_ratio >= 4.5);
});
