import { expect, test } from "@playwright/test";

const criticalAssets = [
  "/assets/branding/shadowgrid-logo-horizontal-dark.svg",
  "/assets/global/global-landing-desktop-day-v1-1280.webp",
  "/assets/global/global-landing-desktop-night-v1-1280.webp",
  "/assets/global/global-login-desktop-v1-1280.webp",
  "/assets/global/global-registration-desktop-v1-1280.webp",
  "/assets/global/global-world-selection-desktop-v1-1280.webp",
  "/assets/global/global-command-center-premium-night-v2-1280.webp",
  "/assets/global/global-exchange-terminal-premium-night-v2-1280.webp",
  "/assets/cities/city-koeln-desktop-day-v1-1280.webp",
  "/assets/maps/map-map-background-day-v1.svg",
] as const;

test("production serves real artwork instead of the SPA fallback", async ({
  page,
  request,
}) => {
  test.skip(
    !process.env.PRODUCTION_BASE_URL,
    "This smoke test is reserved for the deployed alpha environment.",
  );

  for (const asset of criticalAssets) {
    const response = await request.get(asset);
    expect(response.ok(), asset).toBeTruthy();
    expect(response.headers()["content-type"], asset).toMatch(/^image\//);
    expect((await response.body()).byteLength, asset).toBeGreaterThan(500);
  }

  for (const route of ["/", "/login", "/register"] as const) {
    await page.goto(route);
    const backdrop = page.locator("picture img").first();
    await expect(backdrop).toBeVisible();
    await expect
      .poll(() =>
        backdrop.evaluate(
          (image: HTMLImageElement) =>
            image.complete && image.naturalWidth > 0 && image.naturalHeight > 0,
        ),
      )
      .toBe(true);
  }
});
