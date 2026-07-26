import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const openGermanyMap = async (page: Page) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ access_token: "e2e-map-token" }),
    }),
  );
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "e2e-map-user",
        email: "map@example.invalid",
        display_name: "Map Reviewer",
        locale: "en",
        email_verified: true,
        is_admin: false,
        is_moderator: false,
      }),
    }),
  );
  await page.route("**/api/v1/profiles/me", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "map-profile",
        world_id: "world-1",
        city_id: "city-1",
        codename: "Map Reviewer",
        archetype: "family_network",
        home_district_id: "district-1",
        tutorial_step: 7,
        loyalty: 72,
        legitimacy: 68,
        fear: 18,
        investigation_pressure: 24,
        stress: 14,
        stability: 79,
        operation_slots: 3,
        protected_until: "2026-08-01T00:00:00Z",
        recovery_until: null,
        resources: {
          cash: 120000,
          capital: 45000,
          influence: 32,
          intelligence: 21,
          logistics_capacity: 10,
          personnel_capacity: 12,
          version: 1,
        },
      }),
    }),
  );
  await page.goto("/germany");
  await expect(
    page.getByRole("heading", { name: "Germany strategy map" }),
  ).toBeVisible();
};

test("licensed Germany map assets load and remain keyboard operable", async ({
  page,
}, testInfo) => {
  await openGermanyMap(page);

  const background = page.locator(".germany-map__background");
  const layers = page.locator(".germany-map__layer");
  const legend = page.locator(".germany-map-legend-preview");

  await expect(layers).toHaveCount(4);
  await expect
    .poll(() =>
      page
        .locator(
          ".germany-map__background, .germany-map__layer, .germany-map-legend-preview",
        )
        .evaluateAll((images: HTMLImageElement[]) =>
          images.every(
            (image) =>
              image.complete &&
              image.naturalWidth > 0 &&
              image.naturalHeight > 0,
          ),
        ),
    )
    .toBe(true);
  await expect(background).toHaveAttribute(
    "src",
    "/assets/maps/map-map-background-night-v1.svg",
  );
  await page.getByRole("button", { name: "Day" }).click();
  await expect(background).toHaveAttribute(
    "src",
    "/assets/maps/map-map-background-day-v1.svg",
  );
  await page.getByRole("button", { name: "Authority activity" }).click();
  await expect(legend).toHaveAttribute(
    "src",
    "/assets/maps/map-heatmap-authority-legend-v1.svg",
  );

  await expect(
    page.getByLabel("Accessible five-step intensity scale"),
  ).toContainText("Very high");
  await expect(page.getByLabel("Map data attribution")).toContainText(
    "dl-de/by-2-0",
  );
  await page.getByText("Marker and control-point key").click();
  const markerImages = page.locator(".germany-map-marker-groups img");
  await expect(markerImages).toHaveCount(19);
  await expect
    .poll(() =>
      markerImages.evaluateAll((images: HTMLImageElement[]) =>
        images.every(
          (image) =>
            image.complete && image.naturalWidth > 0 && image.naturalHeight > 0,
        ),
      ),
    )
    .toBe(true);
  await page.getByText("Marker and control-point key").click();
  await page.getByText("Premium city packages").click();
  const cityPackage = page.locator(".germany-city-package");
  await expect(cityPackage).toHaveCount(7);
  await expect(cityPackage.locator("picture source")).toHaveCount(42);
  const cityImages = cityPackage.locator("img");
  await expect(cityImages).toHaveCount(21);
  for (let index = 0; index < 7; index += 1) {
    const packageArticle = cityPackage.nth(index);
    await packageArticle.scrollIntoViewIfNeeded();
    await expect
      .poll(
        () =>
          packageArticle
            .locator("img")
            .evaluateAll((images: HTMLImageElement[]) =>
              images.every(
                (image) =>
                  image.complete &&
                  image.naturalWidth > 0 &&
                  image.naturalHeight > 0,
              ),
            ),
        { timeout: 30_000 },
      )
      .toBe(true);
  }
  await page.getByText("Premium city packages").click();
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

  if (process.env.SHADOWGRID_CAPTURE_ASSETS === "1") {
    const viewport = testInfo.project.name === "mobile" ? "mobile" : "desktop";
    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: path.resolve(
        process.cwd(),
        "../../assets/previews",
        `germany-map-${viewport}.png`,
      ),
    });
  }
});
