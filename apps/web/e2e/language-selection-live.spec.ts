import { expect, test } from "@playwright/test";

test("language can be selected at entry and remains selected", async ({
  page,
}) => {
  test.skip(
    !process.env.PRODUCTION_BASE_URL,
    "This smoke test is reserved for the deployed alpha environment.",
  );

  await page.goto("/");
  const language = page.locator("#public-language-selector");
  await expect(language).toBeVisible();
  await expect(language.locator('option[value="en"]')).toHaveCount(1);
  await expect(language.locator('option[value="de"]')).toHaveCount(1);

  await language.selectOption("de");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(
    page.getByRole("heading", {
      name: "Eine Stadt ist ein System. Finde heraus, wo es nachgibt.",
    }),
  ).toBeVisible();

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.locator("#public-language-selector")).toHaveValue("de");

  await page.goto("/register");
  await expect(page.locator("#public-language-selector")).toHaveValue("de");
  await expect(
    page.getByRole("heading", { name: "Konto erstellen" }),
  ).toBeVisible();

  await page.locator("#public-language-selector").selectOption("en");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});
