import { readFileSync, writeFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

type Manifest = {
  requiredLocales: string[];
  rtlLocales: string[];
  localeMetadata: Record<
    string,
    { name: string; script: string; direction: "ltr" | "rtl" }
  >;
};

type GateResult = {
  locale: string;
  direction: "ltr" | "rtl";
  profile: "desktop" | "mobile";
  route: string;
  renderState: "ready" | "loading";
  horizontalOverflow: boolean;
  clippedElements: string[];
};

const testDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(testDirectory, "../../..");
const reportPath = resolve(
  projectRoot,
  "assets/reports/visual-locale-layout-gate.json",
);
const manifest = JSON.parse(
  readFileSync(
    resolve(projectRoot, "packages/i18n/locales/manifest.json"),
    "utf8",
  ),
) as Manifest;
const requestedLocales = process.env.SHADOWGRID_VISUAL_LOCALES?.split(",")
  .map((locale) => locale.trim())
  .filter(Boolean);
const localesUnderTest = requestedLocales?.length
  ? manifest.requiredLocales.filter((locale) =>
      requestedLocales.includes(locale),
    )
  : manifest.requiredLocales;
const credentials = Object.fromEntries(
  readFileSync(resolve(projectRoot, ".local/demo-credentials.txt"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split("=", 2)),
);
const profiles = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 360, height: 800 },
] as const;
const routes = ["/", "/command", "/exchange"] as const;
const routeRoots = {
  "/": ".hero--landing",
  "/command": ".page--command",
  "/exchange": ".page--exchange",
} as const;

async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email address").fill("advanced@example.com");
  await page.getByLabel("Password").fill(credentials["advanced@example.com"]!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("main h1").first()).toBeVisible();
}

async function navigateClient(
  page: Page,
  route: (typeof routes)[number],
): Promise<void> {
  await page.evaluate((nextRoute) => {
    window.history.pushState({}, "", nextRoute);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, route);
  await expect(page).toHaveURL(new RegExp(`${route === "/" ? "/$" : route}$`));
  await expect(page.locator(routeRoots[route]).first()).toBeVisible();
  await expect(page.locator("main h1").first()).toBeVisible();
}

async function inspectLayout(page: Page): Promise<{
  horizontalOverflow: boolean;
  clippedElements: string[];
}> {
  return page.evaluate(() => {
    const root = document.documentElement;
    const selector = [
      "main h1",
      "main h2",
      "main h3",
      "main button",
      "main label",
      "main th",
      ".metric__label",
      ".status-chip",
      ".exchange-market-rail__symbol",
      ".landing-capability-rail strong",
    ].join(",");
    const clippedElements = [
      ...document.querySelectorAll<HTMLElement>(selector),
    ]
      .filter((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        if (
          style.display === "none" ||
          style.visibility === "hidden" ||
          rect.width === 0 ||
          rect.height === 0 ||
          element.closest(".table-wrap")
        )
          return false;
        const clipsX = ["hidden", "clip"].includes(style.overflowX);
        const clipsY = ["hidden", "clip"].includes(style.overflowY);
        const range = document.createRange();
        range.selectNodeContents(element);
        const textRects = [...range.getClientRects()].filter(
          (textRect) => textRect.width > 0 && textRect.height > 0,
        );
        const contentLeft = rect.left + Number.parseFloat(style.paddingLeft);
        const contentRight = rect.right - Number.parseFloat(style.paddingRight);
        const contentTop = rect.top + Number.parseFloat(style.paddingTop);
        const contentBottom =
          rect.bottom - Number.parseFloat(style.paddingBottom);
        const textClippedX = textRects.some(
          (textRect) =>
            textRect.left < contentLeft - 2 ||
            textRect.right > contentRight + 2,
        );
        const textClippedY = textRects.some(
          (textRect) =>
            textRect.top < contentTop - 2 ||
            textRect.bottom > contentBottom + 2,
        );
        return (
          (clipsX && textClippedX) ||
          (clipsY && textClippedY) ||
          rect.left < -1 ||
          rect.right > window.innerWidth + 1
        );
      })
      .map((element) => {
        const text = element.textContent?.trim().replace(/\s+/g, " ") ?? "";
        return `${element.tagName.toLowerCase()}.${element.className}:${text.slice(0, 80)}`;
      });
    return {
      horizontalOverflow: root.scrollWidth > root.clientWidth + 1,
      clippedElements,
    };
  });
}

async function applyLocaleStress(
  page: Page,
  locale: string,
  direction: "ltr" | "rtl",
  nativeName: string,
): Promise<void> {
  await page.evaluate(
    ({ locale: nextLocale, direction: nextDirection, nativeName: name }) => {
      document.documentElement.lang = nextLocale;
      document.documentElement.dir = nextDirection;
      const targets = document.querySelectorAll<HTMLElement>(
        "main h1, main h2, main h3, main button, main label, .metric__label, .landing-capability-rail strong",
      );
      targets.forEach((element, index) => {
        const source = element.textContent?.trim().replace(/\s+/g, " ");
        if (!source) return;
        const expansion =
          index % 2 === 0 ? `${name} · ${source} · ${name}` : name;
        element.textContent = expansion;
      });
    },
    { locale, direction, nativeName },
  );
}

test("all 36 locales pass reference-screen desktop, mobile and RTL layout gates", async ({
  page,
}) => {
  test.setTimeout(1_800_000);
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await login(page);
  const results: GateResult[] = [];

  for (const profile of profiles) {
    await page.setViewportSize({
      width: profile.width,
      height: profile.height,
    });
    for (const locale of localesUnderTest) {
      const direction = manifest.rtlLocales.includes(locale) ? "rtl" : "ltr";
      const nativeName = manifest.localeMetadata[locale]?.name ?? locale;
      for (const route of routes) {
        await test.step(`${profile.name} ${locale} ${route}`, async () => {
          await navigateClient(page, route);
          await applyLocaleStress(page, locale, direction, nativeName);
          await expect(page.locator("html")).toHaveAttribute("lang", locale);
          await expect(page.locator("html")).toHaveAttribute("dir", direction);
          await expect(page.locator(".state--error")).toHaveCount(0);
          const renderState =
            (await page.locator(".spinner").count()) > 0 ? "loading" : "ready";
          const layout = await inspectLayout(page);
          expect(
            layout.horizontalOverflow,
            `${profile.name} ${locale} ${route} horizontal overflow`,
          ).toBe(false);
          expect(
            layout.clippedElements,
            `${profile.name} ${locale} ${route} clipped controls or headings`,
          ).toEqual([]);
          results.push({
            locale,
            direction,
            profile: profile.name,
            route,
            renderState,
            ...layout,
          });
        });
      }
      if (profile.name === "desktop") {
        const axe = await new AxeBuilder({ page }).analyze();
        expect(
          axe.violations.filter((item) =>
            ["serious", "critical"].includes(item.impact ?? ""),
          ),
          `${locale} serious/critical Axe findings`,
        ).toEqual([]);
      }
    }
  }

  expect(results).toHaveLength(localesUnderTest.length * 6);
  await mkdir(dirname(reportPath), { recursive: true });
  writeFileSync(
    reportPath,
    `${JSON.stringify(
      {
        schemaVersion: 1,
        generatedAt: new Date().toISOString(),
        localeCount: localesUnderTest.length,
        catalogMode: "layout-stress-with-configured-locale-metadata",
        routeCount: routes.length,
        profileCount: profiles.length,
        resultCount: results.length,
        passed: true,
        results,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
});
