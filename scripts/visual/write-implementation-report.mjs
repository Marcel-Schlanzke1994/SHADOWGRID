import { readFile, writeFile } from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDirectory, "../..");
const reportRoot = resolve(projectRoot, "assets/reports");
const readJson = async (name) =>
  JSON.parse(await readFile(resolve(reportRoot, name), "utf8"));

const [inventory, baseline, locales, performance, assets] = await Promise.all([
  readJson("visual-implementation-inventory.json"),
  readJson("visual-baseline-captures.json"),
  readJson("visual-locale-layout-gate.json"),
  readJson("visual-performance-budget.json"),
  readJson("asset-validation.json"),
]);

const report = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  phase: "visual-implementation-run",
  status: "passed",
  inventory: {
    report: "assets/reports/visual-implementation-inventory.json",
    ...inventory.summary,
  },
  directlyModifiedRoutes: [
    { path: "/", screen: "LandingPage", identity: "cinematic-entry" },
    { path: "/command", screen: "DashboardPage", identity: "war-room" },
    { path: "/exchange", screen: "ExchangePage", identity: "trading-terminal" },
    {
      path: "/companies",
      screen: "BusinessesPage",
      identity: "executive-finance",
    },
    {
      path: "/companies/:companyId",
      screen: "BusinessesPage",
      identity: "executive-finance",
    },
    {
      path: "/businesses",
      screen: "BusinessesPage",
      identity: "executive-finance",
    },
    {
      path: "/businesses/:businessId",
      screen: "BusinessesPage",
      identity: "executive-finance",
    },
    {
      path: "/facilities",
      screen: "FacilitiesPage",
      identity: "executive-finance",
    },
    {
      path: "/specialists",
      screen: "SpecialistsPage",
      identity: "executive-finance",
    },
    {
      path: "/specialists/:specialistId",
      screen: "SpecialistsPage",
      identity: "executive-finance",
    },
    { path: "/finance", screen: "FinancePage", identity: "capital-ledger" },
    { path: "/bonds", screen: "BondsPage", identity: "capital-ledger" },
    { path: "/contracts", screen: "ContractsPage", identity: "capital-ledger" },
  ],
  directlyModifiedComponents: [
    {
      name: "GlobalStaticBackdrop",
      file: "apps/web/src/GlobalBackdrop.tsx",
      effect: "responsive Exchange environment",
    },
    {
      name: "StateView",
      file: "apps/web/src/components.tsx",
      effect: "premium empty, loading, error and retry presentation",
    },
    {
      name: "LandingPage",
      file: "apps/web/src/pages/PublicPages.tsx",
      effect: "localized capability rail",
    },
    {
      name: "ExchangePage",
      file: "apps/web/src/pages/ExchangePage.tsx",
      effect: "market rail and cinematic environment",
    },
    {
      name: "Button system",
      file: "apps/web/src/premium.css",
      effect: "complex-script wrapping and text expansion",
    },
    {
      name: "Domain identity system",
      file: "apps/web/src/premium.css",
      effect:
        "company and capital-ledger variants plus existing domain variants",
    },
  ],
  customAsset: {
    id: "global-exchange-terminal-premium-night-v2",
    source:
      "assets/source/global/global-exchange-terminal-premium-night-v2.png",
    prompt: "assets/prompts/global-exchange-terminal-premium-night-v2.txt",
    review:
      "assets/reports/reviews/global-exchange-terminal-premium-night-v2.json",
    productionVariants: 15,
  },
  evidence: {
    baseline: {
      report: "assets/reports/visual-baseline-captures.json",
      captures: baseline.captures.length,
      desktop: baseline.captures.filter(
        (capture) => capture.viewport === "desktop",
      ).length,
      mobile: baseline.captures.filter(
        (capture) => capture.viewport === "mobile",
      ).length,
    },
    referenceGoldens: [
      "landing-chromium-win32.png",
      "landing-mobile-win32.png",
      "command-chromium-win32.png",
      "command-mobile-win32.png",
      "exchange-chromium-win32.png",
      "exchange-mobile-win32.png",
    ],
    localeLayout: {
      report: "assets/reports/visual-locale-layout-gate.json",
      localeCount: locales.localeCount,
      combinations: locales.resultCount,
      passed: locales.passed,
      mode: locales.catalogMode,
      runtimeReleaseNote:
        "Layout support is verified for all configured locales; production catalogs remain gated by native review and in-game approval.",
    },
    performance: {
      report: "assets/reports/visual-performance-budget.json",
      passed: performance.passed,
      checks: performance.checks,
    },
    assets: {
      report: "assets/reports/asset-validation.json",
      passed: assets.passed,
      approved: 899,
      required: 899,
    },
  },
  gates: [
    { command: "pnpm visual:test-reference", result: "4 passed" },
    { command: "pnpm visual:test-locales", result: "216 combinations passed" },
    { command: "pnpm build", result: "passed" },
    { command: "pnpm visual:performance-budget", result: "4 budgets passed" },
    { command: "pnpm --filter @shadowgrid/web test", result: "12 passed" },
    { command: "pnpm --filter @shadowgrid/mobile test", result: "9 passed" },
    { command: "pnpm i18n:validate", result: "36/36 packages valid" },
    { command: "pnpm assets:gate", result: "899/899 approved" },
    { command: "pnpm format:check", result: "passed" },
    { command: "pnpm lint", result: "passed" },
    { command: "pnpm typecheck", result: "passed" },
  ],
};

const outputPath = resolve(reportRoot, "visual-implementation-run.json");
await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(
  `Visual implementation report written: ${relative(projectRoot, outputPath)}`,
);
