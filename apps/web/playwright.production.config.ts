import { defineConfig, devices } from "@playwright/test";

const liveBaseUrl = process.env.PRODUCTION_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  testMatch: [
    "production-localization.spec.ts",
    "alpha-registration-live.spec.ts",
    "language-selection-live.spec.ts",
    "production-assets-live.spec.ts",
    "production-route-matrix-live.spec.ts",
    "production-mutation-live.spec.ts",
  ],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: liveBaseUrl ?? "http://127.0.0.1:4173",
    ...devices["Desktop Chrome"],
  },
  webServer: liveBaseUrl
    ? undefined
    : {
        command:
          "pnpm --filter @shadowgrid/web preview --host 127.0.0.1 --port 4173",
        url: "http://127.0.0.1:4173",
        cwd: "../..",
        reuseExistingServer: false,
        timeout: 120_000,
      },
});
