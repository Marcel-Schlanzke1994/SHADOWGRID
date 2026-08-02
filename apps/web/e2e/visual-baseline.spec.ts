import { readFileSync, writeFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const testDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(testDirectory, "../../..");
const outputRoot = resolve(projectRoot, "assets/previews/visual-run/baseline");
const reportPath = resolve(
  projectRoot,
  "assets/reports/visual-baseline-captures.json",
);
const credentials = Object.fromEntries(
  readFileSync(resolve(projectRoot, ".local/demo-credentials.txt"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split("=", 2)),
);

const publicRoutes = [
  ["landing", "/"],
  ["login", "/login"],
  ["register", "/register"],
  ["forgot-password", "/forgot-password"],
] as const;

const protectedRoutes = [
  ["worlds", "/worlds"],
  ["tutorial", "/tutorial"],
  ["command", "/command"],
  ["engagement", "/engagement"],
  ["legacy", "/legacy"],
  ["city", "/city"],
  ["germany", "/germany"],
  ["companies", "/companies"],
  ["exchange", "/exchange"],
  ["facilities", "/facilities"],
  ["specialists", "/specialists"],
  ["operations", "/operations"],
  ["network", "/network"],
  ["intelligence", "/intelligence"],
  ["investigation", "/investigation"],
  ["cartels", "/cartels"],
  ["diplomacy", "/diplomacy"],
  ["pvp", "/pvp"],
  ["territories", "/territories"],
  ["wars", "/wars"],
  ["alliances", "/alliances"],
  ["communications", "/communications"],
  ["market", "/market"],
  ["contracts", "/contracts"],
  ["finance", "/finance"],
  ["bonds", "/bonds"],
  ["real-estate", "/real-estate"],
  ["research", "/research"],
  ["news", "/news"],
  ["rankings", "/rankings"],
  ["settings", "/settings"],
  ["admin", "/admin"],
  ["moderation", "/moderation"],
] as const;

const viewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 412, height: 915 },
] as const;

type Capture = {
  viewport: string;
  route: string;
  file: string;
  error_state: boolean;
};

async function settle(page: Page): Promise<void> {
  await expect(page.locator("main").first()).toBeVisible();
  await expect(page.locator("main h1").first()).toBeVisible();
  await page.locator("img").evaluateAll(async (images) => {
    await Promise.race([
      Promise.all(
        images.map((image) =>
          image instanceof HTMLImageElement
            ? image.decode().catch(() => undefined)
            : Promise.resolve(),
        ),
      ),
      new Promise<void>((resolveTimeout) => {
        window.setTimeout(resolveTimeout, 3_000);
      }),
    ]);
  });
  await page.waitForTimeout(120);
}

async function capture(
  page: Page,
  viewport: (typeof viewports)[number],
  id: string,
  route: string,
  captures: Capture[],
): Promise<void> {
  await page.goto(route);
  await settle(page);
  const file = resolve(outputRoot, viewport.name, `${id}.png`);
  await page.screenshot({
    path: file,
    fullPage: false,
    animations: "disabled",
    caret: "hide",
  });
  captures.push({
    viewport: viewport.name,
    route,
    file: `assets/previews/visual-run/baseline/${viewport.name}/${id}.png`,
    error_state: (await page.locator(".state--error").count()) > 0,
  });
}

async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("advanced@example.com");
  await page.getByLabel("Password").fill(credentials["advanced@example.com"]!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Command center" }),
  ).toBeVisible();
}

async function captureViewport(
  page: Page,
  viewport: (typeof viewports)[number],
  captures: Capture[],
): Promise<void> {
  for (const [id, route] of publicRoutes) {
    await capture(page, viewport, id, route, captures);
  }
  await login(page);
  for (const [id, route] of protectedRoutes) {
    await capture(page, viewport, id, route, captures);
  }
}

test("capture the complete visual implementation baseline", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.SHADOWGRID_CAPTURE_VISUAL_BASELINE !== "1",
    "Baseline capture is explicit.",
  );
  test.setTimeout(600_000);
  const viewport =
    testInfo.project.name === "mobile" ? viewports[1] : viewports[0];
  await page.setViewportSize({
    width: viewport.width,
    height: viewport.height,
  });
  const captures: Capture[] = [];
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await mkdir(resolve(outputRoot, viewport.name), { recursive: true });
  await captureViewport(page, viewport, captures);
  writeFileSync(
    reportPath.replace(".json", `-${viewport.name}.json`),
    `${JSON.stringify(
      {
        schema_version: 1,
        source: "functioning-local-application",
        seeded_account: "advanced-demo-persona",
        captures,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  expect(captures).toHaveLength(publicRoutes.length + protectedRoutes.length);
});
