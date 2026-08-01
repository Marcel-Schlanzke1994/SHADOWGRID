import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

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

const routes = [
  { path: "/worlds", purpose: "world selection" },
  { path: "/tutorial", purpose: "tutorial" },
  { path: "/command", purpose: "command center" },
  { path: "/engagement", purpose: "voluntary engagement controls" },
  { path: "/legacy", purpose: "chronicle and legacy" },
  { path: "/city", purpose: "city and districts" },
  { path: "/germany", purpose: "Germany map" },
  { path: "/companies", purpose: "company portfolio" },
  { path: "/exchange", purpose: "stock exchange" },
  { path: "/facilities", purpose: "facilities" },
  { path: "/specialists", purpose: "specialists" },
  { path: "/operations", purpose: "operations" },
  { path: "/network", purpose: "network" },
  { path: "/intelligence", purpose: "intelligence" },
  { path: "/investigation", purpose: "investigation" },
  { path: "/cartels", purpose: "cartels" },
  { path: "/diplomacy", purpose: "diplomacy" },
  { path: "/pvp", purpose: "strategic actions" },
  { path: "/territories", purpose: "territories" },
  { path: "/wars", purpose: "wars" },
  { path: "/alliances", purpose: "alliances" },
  { path: "/communications", purpose: "communications" },
  { path: "/market", purpose: "resource market" },
  { path: "/contracts", purpose: "contracts" },
  { path: "/finance", purpose: "company finance" },
  { path: "/bonds", purpose: "bonds" },
  { path: "/real-estate", purpose: "real estate" },
  { path: "/research", purpose: "research" },
  { path: "/news", purpose: "news and notifications" },
  { path: "/rankings", purpose: "rankings" },
  { path: "/settings", purpose: "settings" },
  { path: "/admin", purpose: "administrator boundary" },
  { path: "/moderation", purpose: "moderation boundary" },
] as const;

const login = async (page: Page) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("advanced@example.com");
  await page.getByLabel("Password").fill(credentials["advanced@example.com"]!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Command center" }),
  ).toBeVisible();
};

test("every primary page has landmarks and no serious automated accessibility violation", async ({
  page,
}) => {
  test.setTimeout(600_000);
  await login(page);

  for (const route of [...routes].reverse()) {
    await test.step(`${route.purpose}: ${route.path}`, async () => {
      await page.goto(route.path);
      const main = page.locator("main").first();
      await expect(main).toBeVisible();
      await expect(main.locator("h1").first()).toBeVisible();
      const results = await new AxeBuilder({ page }).analyze();
      expect(
        results.violations.filter((item) =>
          ["serious", "critical"].includes(item.impact ?? ""),
        ),
        `${route.path} serious/critical Axe findings`,
      ).toEqual([]);
    });
  }
});

test("skip navigation, reduced motion and pseudo-locales remain operable", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await login(page);
  await page.goto("/command");
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await skipLink.focus();
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  const reducedDurations = await page.locator("#main").evaluate((element) => {
    const style = getComputedStyle(element);
    return [style.animationDuration, style.transitionDuration];
  });
  expect(["0.01ms", "1e-05s"]).toContain(reducedDurations[0]);
  expect(["0.01ms", "1e-05s"]).toContain(reducedDurations[1]);

  await page.goto("/settings");
  await page.locator("#field-language").selectOption("en-XA");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await page.locator("#field-language").selectOption("ar-XB");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});
