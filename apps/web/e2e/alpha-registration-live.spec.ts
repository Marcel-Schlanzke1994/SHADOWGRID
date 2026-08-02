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

  await expect(page).toHaveURL(/\/(?:command|worlds)(?:[/?#]|$)/);

  const cleanup = await request.delete("/api/v1/privacy/account", {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  expect(cleanup.ok()).toBeTruthy();
});
