import { defineConfig, devices } from "@playwright/test";

const liveBaseUrl = process.env.PRODUCTION_BASE_URL;
if (!liveBaseUrl) {
  throw new Error("PRODUCTION_BASE_URL is required for the live UI suite.");
}

export default defineConfig({
  testDir: "./e2e",
  testIgnore: [
    "accessibility-matrix.spec.ts",
    "critical-flow.spec.ts",
    "alpha-registration-live.spec.ts",
    "language-selection-live.spec.ts",
    "production-assets-live.spec.ts",
    "production-localization.spec.ts",
    "production-mutation-live.spec.ts",
    "production-route-matrix-live.spec.ts",
    "visual-baseline.spec.ts",
    "visual-locales.spec.ts",
    "visual-reference.spec.ts",
  ],
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 2,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: liveBaseUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
