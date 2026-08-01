import assert from "node:assert/strict";
import test from "node:test";

import { main } from "./smoke-test.mjs";

test("local smoke dry-run is deterministic and sends no requests", async () => {
  const result = await main([
    "--target=local",
    "--base-url=http://127.0.0.1:8000",
    "--dry-run",
  ]);

  assert.equal(result.mode, "dry-run");
  assert.equal(result.network_requests_sent, false);
  assert.equal(result.checks.length, 8);
});

test("non-local smoke plan rejects insecure and local URLs", async () => {
  await assert.rejects(
    main([
      "--target=staging",
      "--base-url=http://staging.shadowgrid.example",
      "--dry-run",
    ]),
    /public HTTPS URL/,
  );
  await assert.rejects(
    main([
      "--target=production",
      "--base-url=https://localhost",
      "--dry-run",
    ]),
    /public HTTPS URL/,
  );
});
