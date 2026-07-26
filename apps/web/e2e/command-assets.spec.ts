import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const capturePreview = async (
  page: Page,
  projectName: string,
  view: "day" | "night" | "offline",
) => {
  if (process.env.SHADOWGRID_CAPTURE_ASSETS !== "1") {
    return;
  }

  const viewport = projectName === "mobile" ? "mobile" : "desktop";
  await page.screenshot({
    animations: "disabled",
    path: path.resolve(
      process.cwd(),
      "../../assets/previews",
      view === "offline"
        ? `global-offline-${viewport}.png`
        : `command-center-${viewport}-${view}.png`,
    ),
  });
};

const openCommandCenter = async (
  page: Page,
  { profileError = false }: { profileError?: boolean } = {},
) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ access_token: "e2e-command-token" }),
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
        email_verified: true,
        is_admin: false,
        is_moderator: false,
      }),
    }),
  );
  await page.route("**/api/v1/profiles/me", (route) => {
    if (profileError) {
      return route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "service.unavailable",
            message: "Service unavailable",
            request_id: "e2e-offline",
          },
          server_time: "2026-07-25T00:00:00Z",
        }),
      });
    }
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "profile-1",
        world_id: "world-1",
        city_id: "city-1",
        codename: "E2E",
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
    });
  });
  await page.route("**/api/v1/operations", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/v1/world-events", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.goto("/command");
  await expect(page.locator(".page--command")).toBeVisible();
};

test("command center loads the responsive daytime artwork", async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ colorScheme: "light" });
  await openCommandCenter(page);
  const backdrop = page.locator(".day-night-backdrop--command img");

  await expect(backdrop).toBeVisible();
  await expect
    .poll(() => backdrop.evaluate((image: HTMLImageElement) => image.complete))
    .toBe(true);
  await backdrop.evaluate((image: HTMLImageElement) => image.decode());
  await expect
    .poll(() =>
      backdrop.evaluate((image: HTMLImageElement) => image.currentSrc),
    )
    .toContain("global-command-center-day-v1");
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
  await capturePreview(page, testInfo.project.name, "day");

  await page.emulateMedia({ colorScheme: "dark" });
  await expect
    .poll(() =>
      backdrop.evaluate((image: HTMLImageElement) => image.currentSrc),
    )
    .toContain("global-command-center-night-v1");
  await expect
    .poll(() =>
      backdrop.evaluate(
        (image: HTMLImageElement) =>
          image.complete && image.naturalWidth > 0 && image.naturalHeight > 0,
      ),
    )
    .toBe(true);
  await backdrop.evaluate((image: HTMLImageElement) => image.decode());
  await capturePreview(page, testInfo.project.name, "night");
});

test("offline state loads its accessible decorative artwork", async ({
  page,
}, testInfo) => {
  await page.addInitScript(() => {
    Object.defineProperty(window.navigator, "onLine", {
      configurable: true,
      get: () => false,
    });
  });
  await openCommandCenter(page, { profileError: true });

  const alert = page.getByRole("alert");
  const backdrop = page.locator(".system-state-backdrop--offline img");
  await expect(
    alert.getByRole("heading", { name: "Connection interrupted" }),
  ).toBeVisible();
  await expect
    .poll(() =>
      backdrop.evaluate((image: HTMLImageElement) => image.currentSrc),
    )
    .toContain("global-offline-v1");
  await expect
    .poll(() =>
      backdrop.evaluate(
        (image: HTMLImageElement) =>
          image.complete && image.naturalWidth > 0 && image.naturalHeight > 0,
      ),
    )
    .toBe(true);
  await backdrop.evaluate((image: HTMLImageElement) => image.decode());
  await expect(backdrop).toHaveAttribute("alt", "");
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
  await capturePreview(page, testInfo.project.name, "offline");
});
