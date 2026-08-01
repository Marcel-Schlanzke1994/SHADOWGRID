import { readFileSync, writeFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";

type Manifest = {
  requiredLocales: string[];
  rtlLocales: string[];
};

type Evidence = {
  locale: string;
  profile: string;
  direction: "ltr" | "rtl";
  route: "/command";
  colorScheme: "light" | "dark";
  viewport: { width: number; height: number };
  file: string;
  checks: ["no-horizontal-overflow", "localized-direction", "visible-heading"];
};

const testDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(testDirectory, "../../..");
const localesRoot = resolve(projectRoot, "packages/i18n/locales");
const outputRoot = resolve(projectRoot, "docs/localization/evidence");
const manifest = JSON.parse(
  readFileSync(resolve(localesRoot, "manifest.json"), "utf8"),
) as Manifest;
const credentials = Object.fromEntries(
  readFileSync(resolve(projectRoot, ".local/demo-credentials.txt"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split("=", 2)),
);

const profiles = [
  {
    name: "mobile-small-light",
    viewport: { width: 320, height: 640 },
    colorScheme: "light",
  },
  {
    name: "mobile-large-dark",
    viewport: { width: 430, height: 932 },
    colorScheme: "dark",
  },
  {
    name: "tablet-light",
    viewport: { width: 1024, height: 1366 },
    colorScheme: "light",
  },
  {
    name: "tablet-dark",
    viewport: { width: 1024, height: 1366 },
    colorScheme: "dark",
  },
  {
    name: "desktop-light",
    viewport: { width: 1440, height: 900 },
    colorScheme: "light",
  },
  {
    name: "desktop-dark",
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
  },
] as const;

const assertReleaseApproved = (): void => {
  const blocked = manifest.requiredLocales.filter((locale) => {
    const review = JSON.parse(
      readFileSync(resolve(localesRoot, locale, "review.json"), "utf8"),
    ) as {
      catalogStatus: string;
      accessibility: { status: string };
    };
    return (
      review.catalogStatus !== "in_game_approved" ||
      review.accessibility.status !== "in_game_approved"
    );
  });
  if (blocked.length)
    throw new Error(
      `Localization capture requires reviewed catalogs and accessibility approval: ${blocked.join(", ")}`,
    );
};

const login = async (page: Page): Promise<void> => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("advanced@example.com");
  await page.getByLabel("Password").fill(credentials["advanced@example.com"]!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("main h1").first()).toBeVisible();
};

const captureProfile = async (
  browser: Browser,
  profile: (typeof profiles)[number],
  evidence: Evidence[],
): Promise<void> => {
  const context = await browser.newContext({
    baseURL: "http://127.0.0.1:5173",
    viewport: profile.viewport,
    colorScheme: profile.colorScheme,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  await login(page);
  for (const locale of manifest.requiredLocales) {
    await test.step(`${profile.name}: ${locale}`, async () => {
      await page.goto("/settings");
      await page.locator("#field-language").selectOption(locale);
      const direction = manifest.rtlLocales.includes(locale) ? "rtl" : "ltr";
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await expect(page.locator("html")).toHaveAttribute("dir", direction);
      await page.goto("/command");
      await expect(page.locator("main h1").first()).toBeVisible();
      await expect(page.locator(".spinner")).toHaveCount(0, {
        timeout: 30_000,
      });
      await expect(page.locator(".state--error")).toHaveCount(0);
      const horizontalOverflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth + 1,
      );
      expect(
        horizontalOverflow,
        `${locale} ${profile.name} horizontal overflow`,
      ).toBe(false);
      if (profile.name === "desktop-light") {
        const results = await new AxeBuilder({ page }).analyze();
        expect(
          results.violations.filter((item) =>
            ["serious", "critical"].includes(item.impact ?? ""),
          ),
          `${locale} serious/critical Axe findings`,
        ).toEqual([]);
      }
      const relativeFile = `docs/localization/evidence/${locale}/${profile.name}.png`;
      const absoluteFile = resolve(projectRoot, relativeFile);
      await mkdir(dirname(absoluteFile), { recursive: true });
      await page.screenshot({ path: absoluteFile, fullPage: true });
      evidence.push({
        locale,
        profile: profile.name,
        direction,
        route: "/command",
        colorScheme: profile.colorScheme,
        viewport: { ...profile.viewport },
        file: relativeFile,
        checks: [
          "no-horizontal-overflow",
          "localized-direction",
          "visible-heading",
        ],
      });
    });
  }
  await context.close();
};

test("capture the 36-locale release matrix", async ({ browser }) => {
  test.setTimeout(1_800_000);
  assertReleaseApproved();
  const evidence: Evidence[] = [];
  for (const profile of profiles)
    await captureProfile(browser, profile, evidence);
  expect(evidence).toHaveLength(36 * profiles.length);
  await mkdir(outputRoot, { recursive: true });
  writeFileSync(
    resolve(outputRoot, "localization-release-matrix.json"),
    `${JSON.stringify({ schemaVersion: 1, evidence }, null, 2)}\n`,
    "utf8",
  );
});
