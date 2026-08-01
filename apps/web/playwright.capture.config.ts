import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.capture.ts",
  timeout: 900_000,
  expect: {
    timeout: 15_000,
  },
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "node scripts/run-python.mjs --cwd apps/api -m uvicorn shadowgrid.main:app --host 0.0.0.0 --port 8000",
      url: "http://127.0.0.1:8000/api/v1/health",
      cwd: "../..",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "pnpm --filter @shadowgrid/web dev",
      url: "http://127.0.0.1:5173",
      cwd: "../..",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
