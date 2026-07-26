import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("landing artwork is responsive, loaded and accessible", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  const heading = page.getByRole("heading", { level: 1 });
  const backdrop = page.locator(".landing-backdrop img");

  await expect(heading).toBeVisible();
  await expect(backdrop).toBeVisible();
  await expect
    .poll(() => backdrop.evaluate((image: HTMLImageElement) => image.complete))
    .toBe(true);
  expect(
    await backdrop.evaluate((image: HTMLImageElement) => image.naturalWidth),
  ).toBeGreaterThan(0);
  await expect
    .poll(() =>
      backdrop.evaluate((image: HTMLImageElement) => image.currentSrc),
    )
    .toContain(
      testInfo.project.name === "mobile"
        ? "global-landing-mobile-day-v1"
        : "global-landing-desktop-day-v1",
    );
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

test("landing artwork selects the matching night variant", async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  const backdrop = page.locator(".landing-backdrop img");
  await expect(backdrop).toBeVisible();
  await expect
    .poll(() =>
      backdrop.evaluate((image: HTMLImageElement) => image.currentSrc),
    )
    .toContain(
      testInfo.project.name === "mobile"
        ? "global-landing-mobile-night-v1"
        : "global-landing-desktop-night-v1",
    );
});

test("landing artwork reflows at 200 percent without horizontal overflow", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name === "mobile", "Desktop zoom reflow check.");
  await page.setViewportSize({ width: 640, height: 900 });
  await page.goto("/");
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });

  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
