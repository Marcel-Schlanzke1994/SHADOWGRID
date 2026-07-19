import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const testDirectory = dirname(fileURLToPath(import.meta.url));
const credentialsPath = resolve(
  testDirectory,
  "../../../.local/demo-credentials.txt",
);
const credentials = Object.fromEntries(
  readFileSync(credentialsPath, "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split("=", 2)),
);

const navigateFromSidebar = async (
  page: import("@playwright/test").Page,
  destination: string,
) => {
  const menu = page.getByRole("button", { name: "Open navigation" });
  const link = page.getByRole("link", { name: destination });
  if ((page.viewportSize()?.width ?? 1024) <= 760) {
    await expect(menu).toBeVisible();
    await menu.click();
    await expect(link).toBeInViewport();
  }
  await link.click();
};

test("login, dashboard, city, businesses and operation planning are reachable", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("advanced@example.com");
  await page.getByLabel("Password").fill(credentials["advanced@example.com"]!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Command center" }),
  ).toBeVisible();
  await navigateFromSidebar(page, "City");
  await expect(
    page.getByRole("heading", { name: "Vesper city layers" }),
  ).toBeVisible();
  await navigateFromSidebar(page, "Businesses");
  await expect(
    page.getByRole("heading", { name: "Business portfolio" }),
  ).toBeVisible();
  await navigateFromSidebar(page, "Operations");
  await expect(
    page.getByRole("heading", { name: "Operations center" }),
  ).toBeVisible();
});

test("authenticated command center has no serious automated accessibility violations", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("advanced@example.com");
  await page.getByLabel("Password").fill(credentials["advanced@example.com"]!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Command center" }),
  ).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("language switch applies RTL direction", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("advanced@example.com");
  await page.getByLabel("Password").fill(credentials["advanced@example.com"]!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Command center" }),
  ).toBeVisible();
  await navigateFromSidebar(page, "Settings");
  await page.getByLabel("Language").selectOption("ar-XB");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});
