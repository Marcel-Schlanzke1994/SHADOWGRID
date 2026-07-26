import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const authPages = [
  {
    name: "login",
    path: "/login",
    desktopAsset: "global-login-desktop-v1",
    mobileAsset: "global-login-mobile-v1",
  },
  {
    name: "registration",
    path: "/register",
    desktopAsset: "global-registration-desktop-v1",
    mobileAsset: "global-registration-mobile-v1",
  },
] as const;

for (const authPage of authPages) {
  test(`${authPage.name} artwork is responsive, loaded and accessible`, async ({
    page,
  }, testInfo) => {
    await page.goto(authPage.path);
    const backdrop = page.locator(".scene-backdrop--auth img");

    await expect(page.locator(".auth-card")).toBeVisible();
    await expect(backdrop).toBeVisible();
    await expect
      .poll(() =>
        backdrop.evaluate(
          (image: HTMLImageElement) =>
            image.complete && image.naturalWidth > 0 && image.naturalHeight > 0,
        ),
      )
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
          ? authPage.mobileAsset
          : authPage.desktopAsset,
      );
    await expect(page.locator(".scene-backdrop--auth")).toHaveCSS(
      "z-index",
      "1",
    );
    await expect(page.locator(".auth-card")).toHaveCSS("z-index", "2");
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

  test(`${authPage.name} artwork reflows at 200 percent`, async ({
    page,
  }, testInfo) => {
    test.skip(testInfo.project.name === "mobile", "Desktop zoom reflow check.");
    await page.setViewportSize({ width: 640, height: 900 });
    await page.goto(authPage.path);
    await page.evaluate(() => {
      document.documentElement.style.zoom = "2";
    });

    await expect(page.locator(".auth-card")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  });
}
