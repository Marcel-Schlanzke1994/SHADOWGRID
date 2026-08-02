import { expect, test } from "@playwright/test";

test("alpha registration requires only name and password", async ({
  page,
  request,
}) => {
  test.skip(
    !process.env.PRODUCTION_BASE_URL,
    "This smoke test is reserved for the deployed alpha environment.",
  );

  const suffix = crypto.randomUUID().replaceAll("-", "").slice(0, 10);
  const displayName = `AlphaBrowser-${suffix}`;
  const password = `Sg!${crypto.randomUUID().replaceAll("-", "")}9a`;

  await page.goto("/register");

  await expect(page.locator("[data-language-selector]")).toBeVisible();
  await page.locator("#public-language-selector").selectOption("de");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.locator('input[name="displayName"]')).toBeVisible();
  await expect(page.locator('input[name="password"]')).toBeVisible();
  await expect(page.locator('input[type="email"]')).toHaveCount(0);
  await expect(page.locator('input[name="terms"]')).toHaveCount(0);

  await page.locator('input[name="displayName"]').fill(displayName);
  await page.locator('input[name="password"]').fill(password);

  const loginResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/login") &&
      response.request().method() === "POST",
  );
  await page.locator('button[type="submit"]').click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok()).toBeTruthy();
  const tokens = (await loginResponse.json()) as { access_token: string };
  const profileHeaders = { Authorization: `Bearer ${tokens.access_token}` };

  try {
    await expect(page).toHaveURL(/\/(?:command|worlds)(?:[/?#]|$)/);
    const protectedLanguage = page.locator("[data-language-selector]");
    await expect(protectedLanguage).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("lang", "de");
    const worldBackdrop = page.locator(".scene-backdrop--world img");
    await expect(worldBackdrop).toBeVisible();
    await expect
      .poll(() =>
        worldBackdrop.evaluate(
          (image: HTMLImageElement) =>
            image.complete && image.naturalWidth > 0 && image.naturalHeight > 0,
        ),
      )
      .toBe(true);

    const germanProfile = await request.get("/api/v1/auth/me", {
      headers: profileHeaders,
    });
    expect(germanProfile.ok()).toBeTruthy();
    expect(((await germanProfile.json()) as { locale: string }).locale).toBe(
      "de",
    );

    const localeUpdatePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/auth/me/locale") &&
        response.request().method() === "PATCH",
    );
    await protectedLanguage.locator("select").selectOption("en");
    const localeUpdate = await localeUpdatePromise;
    expect(localeUpdate.ok()).toBeTruthy();
    expect(
      ((await localeUpdate.json()) as { locale: string }).locale,
    ).toBe("en");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
  } finally {
    const cleanup = await request.delete("/api/v1/privacy/account", {
      headers: profileHeaders,
    });
    expect(cleanup.ok()).toBeTruthy();
  }
});
