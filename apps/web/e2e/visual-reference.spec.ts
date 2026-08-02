import { readFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

const testDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(testDirectory, "../../..");
const candidateRoot = resolve(
  projectRoot,
  "assets/previews/visual-run/candidate",
);
const credentials = Object.fromEntries(
  readFileSync(resolve(projectRoot, ".local/demo-credentials.txt"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split("=", 2)),
);

const viewports = {
  chromium: { name: "desktop", width: 1440, height: 1000 },
  mobile: { name: "mobile", width: 412, height: 915 },
} as const;

async function settle(page: Page): Promise<void> {
  await expect(page.locator("main").first()).toBeVisible();
  await expect(page.locator("main h1").first()).toBeVisible();
  await expect(page.locator(".spinner")).toHaveCount(0, { timeout: 30_000 });
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
}

async function assertVisualGate(page: Page): Promise<void> {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await expect(page.locator(".state--error")).toHaveCount(0);
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
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

async function captureReference(
  page: Page,
  viewport: (typeof viewports)[keyof typeof viewports],
  id: "landing" | "command" | "exchange",
  route: string,
  masks: Locator[] = [],
): Promise<void> {
  await page.goto(route);
  await settle(page);
  await assertVisualGate(page);
  await page.screenshot({
    path: resolve(candidateRoot, viewport.name, `${id}.png`),
    animations: "disabled",
    caret: "hide",
    fullPage: false,
  });
  await expect(page).toHaveScreenshot(`${id}.png`, {
    animations: "disabled",
    caret: "hide",
    maxDiffPixelRatio: 0.01,
    mask: masks,
    maskColor: "#111720",
  });
}

test("Landing, Command Center and Exchange pass the visual reference gate", async ({
  page,
}, testInfo) => {
  test.setTimeout(300_000);
  const viewport = viewports[testInfo.project.name as keyof typeof viewports];
  await page.setViewportSize({
    width: viewport.width,
    height: viewport.height,
  });
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await mkdir(resolve(candidateRoot, viewport.name), { recursive: true });

  await captureReference(page, viewport, "landing", "/");
  await login(page);
  await captureReference(page, viewport, "command", "/command", [
    page.locator(".metric strong"),
    page.locator(".dashboard-grid p, .dashboard-grid small"),
  ]);
  await captureReference(page, viewport, "exchange", "/exchange", [
    page.locator(".exchange-market-rail strong"),
    page.locator(".data-card strong"),
  ]);
});

test("reference screens survive 200% zoom, large type and RTL", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 720, height: 1000 });
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await login(page);
  for (const route of ["/", "/command", "/exchange"] as const) {
    await page.goto(route);
    await expect(page.locator("main h1").first()).toBeVisible();
    await page.evaluate(() => {
      document.documentElement.lang = "ar";
      document.documentElement.dir = "rtl";
      const heading = document.querySelector<HTMLElement>("main h1");
      if (heading)
        heading.textContent =
          "العربية الفصحى الحديثة · مركز القيادة الاستراتيجية المتقدمة";
    });
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await page.evaluate(() => {
      document.documentElement.style.fontSize = "125%";
      document.documentElement.style.zoom = "2";
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
      `${route} overflows at 200% zoom in RTL`,
    ).toBe(true);
    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations.filter((item) =>
        ["serious", "critical"].includes(item.impact ?? ""),
      ),
      `${route} serious/critical Axe findings at 200% zoom in RTL`,
    ).toEqual([]);
  }
});
