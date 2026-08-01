import { readFileSync, writeFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Browser, type Page } from "@playwright/test";

const testDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(testDirectory, "../../..");
const outputDirectory = resolve(projectRoot, "assets/source/marketing");
const reportPath = resolve(
  projectRoot,
  "assets/reports/store-capture-sources.json",
);
const credentials = Object.fromEntries(
  readFileSync(resolve(projectRoot, ".local/demo-credentials.txt"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split("=", 2)),
);

const groups = [
  {
    platform: "google-play",
    viewport: { width: 1024, height: 576 },
    output: { width: 2048, height: 1152 },
    screens: [
      ["marketing-google-play-city-selection-v1", "/worlds"],
      ["marketing-google-play-dashboard-v1", "/command"],
      ["marketing-google-play-city-map-v1", "/city"],
      ["marketing-google-play-pvp-v1", "/pvp"],
      ["marketing-google-play-organization-v1", "/cartels"],
      ["marketing-google-play-organization-conflict-v1", "/wars"],
      ["marketing-google-play-business-v1", "/companies"],
      ["marketing-google-play-ranking-v1", "/rankings"],
    ],
  },
  {
    platform: "app-store-iphone",
    viewport: { width: 645, height: 1398 },
    output: { width: 1290, height: 2796 },
    screens: [
      ["marketing-app-store-iphone-1-v1", "/command"],
      ["marketing-app-store-iphone-2-v1", "/city"],
      ["marketing-app-store-iphone-3-v1", "/companies"],
      ["marketing-app-store-iphone-4-v1", "/exchange"],
      ["marketing-app-store-iphone-5-v1", "/specialists"],
      ["marketing-app-store-iphone-6-v1", "/cartels"],
      ["marketing-app-store-iphone-7-v1", "/intelligence"],
      ["marketing-app-store-iphone-8-v1", "/rankings"],
    ],
  },
  {
    platform: "app-store-ipad",
    viewport: { width: 1024, height: 1366 },
    output: { width: 2048, height: 2732 },
    screens: [
      ["marketing-app-store-ipad-1-v1", "/germany"],
      ["marketing-app-store-ipad-2-v1", "/command"],
      ["marketing-app-store-ipad-3-v1", "/exchange"],
      ["marketing-app-store-ipad-4-v1", "/real-estate"],
    ],
  },
] as const;

type CaptureEvidence = {
  asset_id: string;
  platform: string;
  language: "en-US";
  route: string;
  width: number;
  height: number;
  source: "functioning-local-application";
  seeded_account: "advanced-demo-persona";
  file: string;
};

async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("advanced@example.com");
  await page.getByLabel("Password").fill(credentials["advanced@example.com"]!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Command center" }),
  ).toBeVisible();
}

async function captureGroup(
  browser: Browser,
  group: (typeof groups)[number],
  evidence: CaptureEvidence[],
): Promise<void> {
  const context = await browser.newContext({
    baseURL: "http://127.0.0.1:5173",
    viewport: group.viewport,
    deviceScaleFactor: 2,
    colorScheme: "dark",
    locale: "en-US",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  await login(page);
  for (const [assetId, route] of group.screens) {
    await test.step(`${group.platform}: ${route}`, async () => {
      await page.goto(route);
      await expect(page.locator("main").first()).toBeVisible();
      await expect(page.locator("main h1").first()).toBeVisible();
      await expect(page.locator(".spinner")).toHaveCount(0, {
        timeout: 30_000,
      });
      await expect(page.locator(".state--error")).toHaveCount(0);
      await expect(page.locator("[data-debug]")).toHaveCount(0);
      expect(await page.locator("body").innerText()).not.toContain(
        "advanced@example.com",
      );
      await page.locator("img").evaluateAll(async (images) => {
        await Promise.race([
          Promise.all(
            images.map(async (image) => {
              if (image instanceof HTMLImageElement) {
                await image.decode().catch(() => undefined);
              }
            }),
          ),
          new Promise<void>((resolveTimeout) => {
            window.setTimeout(resolveTimeout, 10_000);
          }),
        ]);
      });
      const file = resolve(outputDirectory, `${assetId}.png`);
      await page.screenshot({
        path: file,
        fullPage: false,
        animations: "disabled",
        caret: "hide",
      });
      evidence.push({
        asset_id: assetId,
        platform: group.platform,
        language: "en-US",
        route,
        width: group.output.width,
        height: group.output.height,
        source: "functioning-local-application",
        seeded_account: "advanced-demo-persona",
        file: `assets/source/marketing/${assetId}.png`,
      });
    });
  }
  await context.close();
}

test("capture real store screenshots from the functioning seeded application", async ({
  browser,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "chromium",
    "One canonical Chromium capture avoids duplicate output.",
  );
  test.setTimeout(900_000);
  await mkdir(outputDirectory, { recursive: true });
  const evidence: CaptureEvidence[] = [];
  for (const group of groups) {
    await captureGroup(browser, group, evidence);
  }
  expect(evidence).toHaveLength(20);
  writeFileSync(
    reportPath,
    `${JSON.stringify(
      {
        project: "shadowgrid",
        generated_at: new Date().toISOString(),
        capture_count: evidence.length,
        captures: evidence,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
});
