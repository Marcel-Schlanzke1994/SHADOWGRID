import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "pnpm dev:api",
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
