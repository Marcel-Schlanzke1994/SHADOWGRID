import { expect, test } from "@playwright/test";

test("production rejects persisted internal and pseudo locales", async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem("shadowgrid.locale", "ar-XB");
  });

  await page.goto("/login");

  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(
    page.getByRole("heading", { name: "Build your network in Cologne" }),
  ).toBeVisible();
});
