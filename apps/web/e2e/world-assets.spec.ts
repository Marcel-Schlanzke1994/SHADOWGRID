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
  await page.route("**/api/v1/world/cities", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{ id: "city-1", name: "Köln" }]),
    }),
  );
  await page.route("**/api/v1/world/cities/city-1/districts", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{ id: "district-1", name: "Innenstadt" }]),
    }),
  );
  await page.route("**/api/v1/players/me/select-city", async (route) => {
    const request = route.request().postDataJSON() as {
      city_id: string;
      home_district_id: string;
    };
    expect(request.city_id).toBe("city-1");
    expect(request.home_district_id).toBe("district-1");
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "profile-1",
        world_id: "world-1",
        city_id: "city-1",
        codename: "Rhein Network",
        archetype: "business_consortium",
        home_district_id: "district-1",
        tutorial_step: 0,
        loyalty: 65,
        legitimacy: 60,
        fear: 5,
        investigation_pressure: 0,
        stress: 0,
        stability: 70,
        operation_slots: 2,
        protected_until: "2026-07-29T12:00:00Z",
        recovery_until: null,
        resources: {
          cash: 80000,
          capital: 25000,
          influence: 10,
          intelligence: 15,
          logistics_capacity: 10,
          personnel_capacity: 8,
          version: 6,
        },
      }),
    });
  });
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

  await page.getByLabel("Codename").fill("Rhein Network");
  await page
    .getByLabel("Organization approach")
    .selectOption("business_consortium");
  await page.getByRole("button", { name: "Start in this city" }).click();
  await expect(page).toHaveURL(/\/tutorial$/);
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
