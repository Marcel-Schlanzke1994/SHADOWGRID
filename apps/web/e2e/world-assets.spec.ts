import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const mockWorldSelectionApi = async (page: Page) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ access_token: "e2e-world-token" }),
    }),
  );
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "e2e-user",
        email: "player@example.invalid",
        display_name: "E2E Player",
        locale: "en",
        role: "player",
      }),
    }),
  );
  await page.route("**/api/v1/worlds", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{ id: "world-1", name: "Vesper One" }]),
    }),
  );
  await page.route("**/api/v1/worlds/world-1/districts", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{ id: "district-1", name: "North Exchange" }]),
    }),
  );
};

test("world selection artwork is responsive, loaded and accessible", async ({
  page,
}, testInfo) => {
  await mockWorldSelectionApi(page);
  await page.goto("/worlds");

  const backdrop = page.locator(".scene-backdrop--world img");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator(".wide-card")).toBeVisible();
  await expect(backdrop).toBeVisible();
  await expect
    .poll(() => backdrop.evaluate((image: HTMLImageElement) => image.complete))
    .toBe(true);
  await backdrop.evaluate((image: HTMLImageElement) => image.decode());
  expect(
    await backdrop.evaluate((image: HTMLImageElement) => image.naturalWidth),
  ).toBeGreaterThan(0);
  await expect
    .poll(() =>
      backdrop.evaluate((image: HTMLImageElement) => image.currentSrc),
    )
    .toContain(
      testInfo.project.name === "mobile"
        ? "global-world-selection-mobile-v1"
        : "global-world-selection-desktop-v1",
    );
  await expect(page.locator(".scene-backdrop--world")).toHaveCSS(
    "z-index",
    "1",
  );
  await expect(page.locator(".wide-card")).toHaveCSS("z-index", "2");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);

  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("world selection artwork reflows at 200 percent", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "Desktop zoom reflow check.");
  await mockWorldSelectionApi(page);
  await page.setViewportSize({ width: 640, height: 900 });
  await page.goto("/worlds");
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });

  await expect(page.locator(".wide-card")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
