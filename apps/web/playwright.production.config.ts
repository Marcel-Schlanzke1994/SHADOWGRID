import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "production-localization.spec.ts",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command:
      "pnpm --filter @shadowgrid/web preview --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    cwd: "../..",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
