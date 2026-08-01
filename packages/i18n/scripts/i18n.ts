import { existsSync, statSync } from "node:fs";
import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "@formatjs/icu-messageformat-parser";
import {
  configuredLocales,
  regionalOverlayLocales,
  requiredLocales,
  rtlLocales,
} from "@shadowgrid/game-config";
import ts from "typescript";
import { de } from "../src/de";
import { en } from "../src/en";

type JsonObject = Record<string, unknown>;
type Catalog = Record<string, string>;
type WorkflowStatus =
  | "not_started"
  | "machine_draft"
  | "human_translated"
  | "native_reviewed"
  | "in_game_approved";
type ReviewRole =
  | "leadTranslator"
  | "nativeReviewer"
  | "linguisticQa"
  | "localizationOwner"
  | "domainReviewer"
  | "releaseOwner";
type ApprovalKind = "nativeReview" | "inGameQa" | "release";

interface ReviewApproval {
  reviewerId: string;
  approvedAt: string;
  evidence: string[];
}

interface Manifest {
  schemaVersion: number;
  sourceLocale: string;
  requiredLocales: string[];
  localeMetadata: Record<
    string,
    { name: string; script: string; direction: "ltr" | "rtl" }
  >;
  regionalOverlays: Record<string, string[]>;
  pseudoLocales: string[];
  rtlLocales: string[];
  domains: string[];
  releasePolicy: {
    minimumCoverage: number;
    allowFallback: boolean;
    requireNativeReview: boolean;
    requireInGameApproval: boolean;
    requireAccessibilityApproval: boolean;
    requireStoreSupportAndLegal: boolean;
  };
}

interface LocaleReview {
  schemaVersion: number;
  locale: string;
  catalogStatus: WorkflowStatus;
  defaultKeyStatus: WorkflowStatus;
  keyStatusOverrides: Record<string, WorkflowStatus>;
  sourceIdenticalApprovals: Record<
    string,
    { reason: string; reviewerId: string; approvedAt: string }
  >;
  contextStatus: WorkflowStatus;
  glossaryStatus: WorkflowStatus;
  roles: Record<ReviewRole, string | null>;
  approvals: Record<ApprovalKind, ReviewApproval | null>;
  accessibility: { status: WorkflowStatus; evidence: string[] };
  screenshots: { status: WorkflowStatus; evidence: string[] };
  updatedAt: string | null;
}

interface LocaleCoverage {
  schemaVersion: number;
  locale: string;
  scopes: Record<string, WorkflowStatus>;
}

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(scriptDirectory, "..");
const repositoryRoot = resolve(packageRoot, "..", "..");
const localesRoot = join(packageRoot, "locales");
const manifestPath = join(localesRoot, "manifest.json");
const sourceCatalog: Catalog = Object.fromEntries(
  Object.entries(en).sort(([left], [right]) => left.localeCompare(right)),
);
const germanCatalog: Catalog = Object.fromEntries(
  Object.entries(de).sort(([left], [right]) => left.localeCompare(right)),
);
const workflowStatuses: WorkflowStatus[] = [
  "not_started",
  "machine_draft",
  "human_translated",
  "native_reviewed",
  "in_game_approved",
];
const approvalRoles: Record<ApprovalKind, ReviewRole> = {
  nativeReview: "nativeReviewer",
  inGameQa: "linguisticQa",
  release: "releaseOwner",
};

const readJson = async <T>(path: string): Promise<T> =>
  JSON.parse(await readFile(path, "utf8")) as T;

const writeJson = async (path: string, value: unknown): Promise<void> => {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
};

const sortedCatalog = (catalog: Catalog): Catalog =>
  Object.fromEntries(
    Object.entries(catalog).sort(([left], [right]) =>
      left.localeCompare(right),
    ),
  );

const sameValues = (left: unknown[], right: readonly unknown[]): boolean =>
  JSON.stringify(left) === JSON.stringify([...right]);

const validIsoTimestamp = (value: unknown): value is string =>
  typeof value === "string" &&
  value.trim().length > 0 &&
  Number.isFinite(Date.parse(value));

const validEvidencePath = (value: unknown): value is string => {
  if (typeof value !== "string" || !value.trim()) return false;
  const absolute = resolve(repositoryRoot, value);
  const repositoryRelative = relative(repositoryRoot, absolute);
  if (
    !repositoryRelative ||
    repositoryRelative.startsWith("..") ||
    isAbsolute(repositoryRelative)
  )
    return false;
  try {
    return statSync(absolute).isFile();
  } catch {
    return false;
  }
};

const variablesFor = (message: string): string[] => {
  const variables = new Set<string>();
  const expression = /\{([A-Za-z_][A-Za-z0-9_]*)(?:\s*,|\})/g;
  for (const match of message.matchAll(expression)) {
    if (match[1]) variables.add(match[1]);
  }
  return [...variables].sort();
};

const variableType = (name: string): string => {
  if (
    /^(count|current|total|level|number|days|minutes|periods|scores|rewards)$/i.test(
      name,
    )
  )
    return "integer";
  if (
    /^(amount|cost|fee|price|principal|salary|installment|value)$/i.test(name)
  )
    return "localized monetary or numeric value";
  if (/^(date|until|expires|starts|ends)$/i.test(name))
    return "localized date/time";
  return "text";
};

const domainForKey = (key: string, domains: string[]): string => {
  const value = key.toLowerCase();
  const rules: Array<[string, RegExp]> = [
    [
      "engagement",
      /engagement|returnbriefing|sessionsummary|mastery|mentoring/,
    ],
    ["narrative", /legacy|chronicle|dossier|collection|story|narrative/],
    ["exchange", /exchange|portfolio|order|ipo|dividend|share/],
    ["cartels", /cartel|organization|alliance|treaty|district|war/],
    ["intelligence", /intel|investigat|operation|pvp|strategic/],
    ["seasons", /season|ranking|halloffame|reward/],
    [
      "economy",
      /company|business|econom|specialist|loan|bond|property|finance|contract/,
    ],
    ["auth", /auth|signin|signup|password|session|verify|email|account/],
    ["legal", /privacy|legal|moderation|consent|terms/],
    ["store", /store|patchnote|opengraph/],
    [
      "support",
      /support|error|retry|loading|empty|offline|maintenance|requestid/,
    ],
  ];
  for (const [domain, expression] of rules) {
    if (domains.includes(domain) && expression.test(value)) return domain;
  }
  return "common";
};

const catalogByDomain = (
  catalog: Catalog,
  domains: string[],
): Record<string, Catalog> => {
  const result = Object.fromEntries(
    domains.map((domain) => [domain, {}]),
  ) as Record<string, Catalog>;
  for (const [key, value] of Object.entries(catalog)) {
    const domain = domainForKey(key, domains);
    result[domain]![key] = value;
  }
  return Object.fromEntries(
    domains.map((domain) => [domain, sortedCatalog(result[domain] ?? {})]),
  );
};

const readLocaleCatalog = async (
  locale: string,
  domains: string[],
): Promise<Catalog> => {
  const catalog: Catalog = {};
  for (const domain of domains) {
    const path = join(localesRoot, locale, `${domain}.json`);
    if (!existsSync(path)) continue;
    Object.assign(catalog, await readJson<Catalog>(path));
  }
  return sortedCatalog(catalog);
};

const initialStatusFor = (locale: string): WorkflowStatus => {
  if (locale === "en") return "in_game_approved";
  if (locale === "de") return "human_translated";
  return "not_started";
};

const emptyReview = (locale: string): LocaleReview => {
  const status = initialStatusFor(locale);
  return {
    schemaVersion: 1,
    locale,
    catalogStatus: status,
    defaultKeyStatus: status,
    keyStatusOverrides: {},
    sourceIdenticalApprovals: {},
    contextStatus: "machine_draft",
    glossaryStatus: locale === "en" ? "human_translated" : status,
    roles: {
      leadTranslator: null,
      nativeReviewer: null,
      linguisticQa: null,
      localizationOwner: null,
      domainReviewer: null,
      releaseOwner: null,
    },
    approvals: { nativeReview: null, inGameQa: null, release: null },
    accessibility: {
      status: locale === "en" ? "in_game_approved" : "not_started",
      evidence: [],
    },
    screenshots: { status: "not_started", evidence: [] },
    updatedAt: null,
  };
};

const emptyCoverage = (locale: string): LocaleCoverage => ({
  schemaVersion: 1,
  locale,
  scopes: {
    game: initialStatusFor(locale),
    email:
      locale === "en" || locale === "de" ? "human_translated" : "not_started",
    store:
      locale === "en" || locale === "de" ? "human_translated" : "not_started",
    support: "not_started",
    legal: "not_started",
  },
});

const germanGlossary: Record<string, string> = {
  company: "Unternehmen",
  holding: "Beteiligung",
  share: "Aktie",
  ownership: "Eigentum",
  dividend: "Dividende",
  order_book: "Orderbuch",
  bid: "Gebot",
  tender: "Ausschreibung",
  bond: "Anleihe",
  loan: "Kredit",
  collateral: "Sicherheit",
  ledger: "Hauptbuch",
  district: "Distrikt",
  cartel: "Kartell",
  influence: "Einfluss",
  intelligence: "Aufklärung",
  investigation: "Untersuchung",
  operation: "Operation",
  world_event: "Weltereignis",
  season: "Saison",
  headquarters: "Hauptquartier",
  legacy: "Vermächtnis",
  mastery: "Meisterschaft",
};

const createGlossary = async (locale: string): Promise<JsonObject> => {
  const definitions = await readJson<{ terms: Record<string, string> }>(
    join(localesRoot, "glossary", "terms.json"),
  );
  const status: WorkflowStatus =
    locale === "en" ? "human_translated" : initialStatusFor(locale);
  return {
    schemaVersion: 1,
    locale,
    status,
    entries: Object.fromEntries(
      Object.entries(definitions.terms).map(([term, meaning]) => {
        const sourceTerm = term.replaceAll("_", " ");
        const translation =
          locale === "de" ? (germanGlossary[term] ?? sourceTerm) : sourceTerm;
        return [
          term,
          {
            meaning,
            approved: status === "in_game_approved" ? translation : null,
            proposed:
              status === "not_started" || status === "in_game_approved"
                ? null
                : translation,
            allowedShortForm: null,
            forbidden:
              locale === "de" && term === "ledger"
                ? ["Liste", "Kontoauszug"]
                : [],
            grammaticalGender: null,
            example: null,
            status,
          },
        ];
      }),
    ),
  };
};

const contextScreen = (key: string): string => {
  const value = key.toLowerCase();
  const routes: Array<[RegExp, string]> = [
    [
      /engagement|mastery|mentoring|returnbriefing|sessionsummary/,
      "/engagement",
    ],
    [/legacy|chronicle|dossier|collection/, "/legacy"],
    [/exchange|portfolio|order|ipo|dividend|share/, "/exchange"],
    [/cartel|organization/, "/cartels"],
    [/intel|investigat|strategic/, "/intelligence"],
    [/season|ranking|halloffame/, "/rankings"],
    [/company|business/, "/companies"],
    [/specialist/, "/specialists"],
    [/auth|signin|signup|password|verify/, "/login"],
  ];
  return (
    routes.find(([expression]) => expression.test(value))?.[1] ?? "/shared"
  );
};

const createContext = (): JsonObject => ({
  schemaVersion: 1,
  sourceLocale: "en",
  status: "machine_draft",
  messages: Object.fromEntries(
    Object.entries(sourceCatalog).map(([key, source]) => [
      key,
      {
        source,
        description: `Generated context draft for ${key}; the localization owner must refine it before approval.`,
        screen: contextScreen(key),
        audience: /admin|moderation/i.test(key) ? "staff" : "player",
        tone: /story|narrative|chronicle|legacy/i.test(key)
          ? "atmospheric"
          : "serious",
        variables: Object.fromEntries(
          variablesFor(source).map((variable) => [
            variable,
            variableType(variable),
          ]),
        ),
        maxLength: Math.max(24, Math.ceil(source.length * 1.5)),
        screenshot: null,
        sensitive:
          /privacy|security|password|delete|ledger|loan|bond|order|buy|sell|cost|price|moderation/i.test(
            key,
          ),
      },
    ]),
  ),
});

const generateLoader = async (manifest: Manifest): Promise<void> => {
  const approved: string[] = [];
  for (const locale of manifest.requiredLocales) {
    const review = await readJson<LocaleReview>(
      join(localesRoot, locale, "review.json"),
    );
    if (review.catalogStatus === "in_game_approved") approved.push(locale);
  }
  const identifier = (value: string): string =>
    value.replace(/[^A-Za-z0-9]/g, "_");
  const imports = approved
    .flatMap((locale) =>
      manifest.domains.map(
        (domain) =>
          `import catalog_${identifier(locale)}_${identifier(domain)} from "../locales/${locale}/${domain}.json";`,
      ),
    )
    .join("\n");
  const catalogs = approved
    .map((locale) => {
      const domainCatalogs = manifest.domains
        .map((domain) => `catalog_${identifier(locale)}_${identifier(domain)}`)
        .join(", ");
      return `  ${JSON.stringify(locale)}: mergeCatalogs(${domainCatalogs}),`;
    })
    .join("\n");
  const content = `// Generated by pnpm i18n:bootstrap. Do not edit by hand.\nimport type { RequiredLocale } from "@shadowgrid/game-config";\n${imports}\n\nexport type RuntimeCatalog = Record<string, string>;\n\nconst mergeCatalogs = (...catalogs: RuntimeCatalog[]): RuntimeCatalog =>\n  Object.assign({}, ...catalogs);\n\nexport const runtimeApprovedLocales = ${JSON.stringify(approved)} as const satisfies readonly RequiredLocale[];\nexport const localeMetadata = ${JSON.stringify(manifest.localeMetadata, null, 2)} as const satisfies Record<RequiredLocale, { name: string; script: string; direction: "ltr" | "rtl" }>;\nexport const runtimeApprovedCatalogs: Partial<Record<RequiredLocale, RuntimeCatalog>> = {\n${catalogs}\n};\n`;
  await writeFile(
    join(packageRoot, "src", "catalog-loaders.generated.ts"),
    content,
    "utf8",
  );
};

const bootstrap = async (): Promise<void> => {
  const manifest = await readJson<Manifest>(manifestPath);
  const sourceDomains = catalogByDomain(sourceCatalog, manifest.domains);
  const germanDomains = catalogByDomain(germanCatalog, manifest.domains);
  for (const locale of manifest.requiredLocales) {
    const reviewPath = join(localesRoot, locale, "review.json");
    const review = existsSync(reviewPath)
      ? await readJson<LocaleReview>(reviewPath)
      : emptyReview(locale);
    review.sourceIdenticalApprovals ??= {};
    const existingCatalog = await readLocaleCatalog(locale, manifest.domains);
    if (
      locale !== "en" &&
      locale !== "de" &&
      review.catalogStatus === "machine_draft" &&
      JSON.stringify(existingCatalog) === JSON.stringify(sourceCatalog)
    ) {
      review.catalogStatus = "not_started";
      review.defaultKeyStatus = "not_started";
      review.glossaryStatus = "not_started";
    }
    const generatedDraft =
      review.catalogStatus === "not_started" ||
      review.catalogStatus === "machine_draft";
    for (const domain of manifest.domains) {
      const targetPath = join(localesRoot, locale, `${domain}.json`);
      let catalog = sourceDomains[domain] ?? {};
      if (locale === "de") catalog = germanDomains[domain] ?? {};
      else if (locale !== "en" && !generatedDraft && existsSync(targetPath))
        catalog = await readJson<Catalog>(targetPath);
      await writeJson(targetPath, sortedCatalog(catalog));
    }
    await writeJson(reviewPath, review);
    const coveragePath = join(localesRoot, locale, "coverage.json");
    if (!existsSync(coveragePath))
      await writeJson(coveragePath, emptyCoverage(locale));
    const glossaryPath = join(localesRoot, locale, "glossary.json");
    if (
      !existsSync(glossaryPath) ||
      generatedDraft ||
      locale === "en" ||
      locale === "de"
    )
      await writeJson(glossaryPath, await createGlossary(locale));
  }
  const overlays = [
    ...new Set(Object.values(manifest.regionalOverlays).flat()),
  ].filter((locale) => !manifest.requiredLocales.includes(locale));
  for (const overlay of overlays) {
    const overlayPath = join(localesRoot, "overlays", `${overlay}.json`);
    if (!existsSync(overlayPath))
      await writeJson(overlayPath, {
        schemaVersion: 1,
        locale: overlay,
        status: "machine_draft",
        messages: {},
        formatting: {},
      });
  }
  await writeJson(join(localesRoot, "context.json"), createContext());
  await generateLoader(manifest);
  console.log(
    `Bootstrapped ${manifest.requiredLocales.length} locale packages with ${Object.keys(sourceCatalog).length} source keys across ${manifest.domains.length} domains.`,
  );
};

const listFiles = async (directory: string): Promise<string[]> => {
  const result: string[] = [];
  for (const entry of await readdir(directory)) {
    const path = join(directory, entry);
    const details = await stat(path);
    if (details.isDirectory()) result.push(...(await listFiles(path)));
    else result.push(path);
  }
  return result;
};

const duplicateObjectKeys = async (
  path: string,
  variableName: string,
): Promise<string[]> => {
  const source = ts.createSourceFile(
    path,
    await readFile(path, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const keys: string[] = [];
  const visit = (node: ts.Node): void => {
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      node.name.text === variableName &&
      node.initializer &&
      ts.isObjectLiteralExpression(node.initializer)
    ) {
      for (const property of node.initializer.properties) {
        if (!ts.isPropertyAssignment(property) || !property.name) continue;
        if (ts.isIdentifier(property.name) || ts.isStringLiteral(property.name))
          keys.push(property.name.text);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  const seen = new Set<string>();
  return keys.filter((key) => (seen.has(key) ? true : (seen.add(key), false)));
};

const hardcodedVisibleStrings = async (): Promise<string[]> => {
  const roots = [
    join(repositoryRoot, "apps", "web", "src"),
    join(repositoryRoot, "apps", "mobile", "app"),
  ];
  const files = (
    await Promise.all(
      roots.map(async (root) => (existsSync(root) ? listFiles(root) : [])),
    )
  )
    .flat()
    .filter(
      (path) =>
        path.endsWith(".tsx") && !/[\\/]test[\\/]|\.test\.tsx$/.test(path),
    );
  const violations: string[] = [];
  const visibleAttributes = new Set([
    "alt",
    "aria-label",
    "placeholder",
    "title",
    "label",
    "accessibilityLabel",
    "accessibilityHint",
  ]);
  const containsLetter = (value: string): boolean => /\p{L}/u.test(value);
  for (const path of files) {
    const source = ts.createSourceFile(
      path,
      await readFile(path, "utf8"),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    const add = (node: ts.Node, value: string): void => {
      const normalized = value.replace(/\s+/g, " ").trim();
      if (!normalized || !containsLetter(normalized)) return;
      const position = source.getLineAndCharacterOfPosition(
        node.getStart(source),
      );
      violations.push(
        `${relative(repositoryRoot, path)}:${position.line + 1}:${position.character + 1} ${JSON.stringify(normalized)}`,
      );
    };
    const visit = (node: ts.Node): void => {
      if (ts.isJsxText(node)) add(node, node.text);
      if (
        ts.isJsxExpression(node) &&
        node.expression &&
        (ts.isStringLiteral(node.expression) ||
          ts.isNoSubstitutionTemplateLiteral(node.expression))
      )
        add(node, node.expression.text);
      if (
        ts.isJsxAttribute(node) &&
        ts.isIdentifier(node.name) &&
        visibleAttributes.has(node.name.text) &&
        node.initializer
      ) {
        if (ts.isStringLiteral(node.initializer))
          add(node, node.initializer.text);
        else if (
          ts.isJsxExpression(node.initializer) &&
          node.initializer.expression &&
          (ts.isStringLiteral(node.initializer.expression) ||
            ts.isNoSubstitutionTemplateLiteral(node.initializer.expression))
        )
          add(node, node.initializer.expression.text);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  return violations;
};

const usedMessageKeys = async (): Promise<string[]> => {
  const roots = [
    join(repositoryRoot, "apps", "web", "src"),
    join(repositoryRoot, "apps", "mobile", "app"),
  ];
  const files = (await Promise.all(roots.map((root) => listFiles(root))))
    .flat()
    .filter(
      (path) =>
        /\.(ts|tsx)$/.test(path) && !/[\\/]test[\\/]|\.test\.tsx$/.test(path),
    );
  const keys = new Set<string>();
  for (const path of files) {
    const source = ts.createSourceFile(
      path,
      await readFile(path, "utf8"),
      ts.ScriptTarget.Latest,
      true,
      path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    const visit = (node: ts.Node): void => {
      if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        node.expression.text === "t" &&
        node.arguments[0] &&
        ts.isStringLiteral(node.arguments[0])
      )
        keys.add(node.arguments[0].text);
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  return [...keys].sort();
};

const validateTechnical = async (): Promise<void> => {
  const manifest = await readJson<Manifest>(manifestPath);
  const issues: string[] = [];
  const sourceKeys = Object.keys(sourceCatalog).sort();
  if (manifest.schemaVersion !== 1)
    issues.push("manifest schemaVersion must be 1");
  if (manifest.sourceLocale !== "en") issues.push("sourceLocale must be en");
  if (!sameValues(manifest.requiredLocales, requiredLocales))
    issues.push("manifest requiredLocales differ from game-config");
  if (
    manifest.requiredLocales.length !== 36 ||
    new Set(manifest.requiredLocales).size !== 36
  )
    issues.push("exactly 36 unique required locales are mandatory");
  const overlays = [
    ...new Set(Object.values(manifest.regionalOverlays).flat()),
  ];
  const additionalOverlays = overlays.filter(
    (locale) => !manifest.requiredLocales.includes(locale),
  );
  if (!sameValues(additionalOverlays, regionalOverlayLocales))
    issues.push("regional overlay order differs from game-config");
  if (
    !sameValues(
      manifest.rtlLocales,
      [...rtlLocales].filter((locale) => locale !== "ar-XB"),
    )
  )
    issues.push(
      "manifest must contain exactly the seven production RTL locales",
    );
  if (manifest.releasePolicy.allowFallback)
    issues.push("public locale fallback must remain disabled");
  for (const locale of [
    ...manifest.requiredLocales,
    ...overlays,
    ...manifest.pseudoLocales,
  ]) {
    try {
      Intl.getCanonicalLocales(locale);
    } catch {
      issues.push(`${locale}: invalid BCP 47 locale`);
    }
  }
  for (const locale of manifest.requiredLocales) {
    const metadata = manifest.localeMetadata[locale];
    if (!metadata) issues.push(`${locale}: locale metadata missing`);
    if (
      metadata &&
      (metadata.direction === "rtl") !== manifest.rtlLocales.includes(locale)
    )
      issues.push(`${locale}: direction does not match RTL manifest`);
    const catalog = await readLocaleCatalog(locale, manifest.domains);
    const keys = Object.keys(catalog).sort();
    const missing = sourceKeys.filter((key) => !(key in catalog));
    const unknown = keys.filter((key) => !(key in sourceCatalog));
    if (missing.length)
      issues.push(`${locale}: ${missing.length} missing keys`);
    if (unknown.length)
      issues.push(`${locale}: ${unknown.length} unknown keys`);
    for (const key of sourceKeys) {
      const value = catalog[key];
      if (typeof value !== "string" || !value.trim()) {
        issues.push(`${locale}:${key}: empty value`);
        continue;
      }
      if (/<script|javascript:/i.test(value))
        issues.push(`${locale}:${key}: unsafe value`);
      try {
        parse(value, { ignoreTag: true });
      } catch (error) {
        issues.push(`${locale}:${key}: invalid ICU (${String(error)})`);
      }
      if (
        !sameValues(variablesFor(value), variablesFor(sourceCatalog[key] ?? ""))
      )
        issues.push(`${locale}:${key}: placeholder mismatch`);
    }
    const review = await readJson<LocaleReview>(
      join(localesRoot, locale, "review.json"),
    );
    if (
      review.locale !== locale ||
      !workflowStatuses.includes(review.catalogStatus)
    )
      issues.push(`${locale}: invalid review record`);
    const coverage = await readJson<LocaleCoverage>(
      join(localesRoot, locale, "coverage.json"),
    );
    if (coverage.locale !== locale)
      issues.push(`${locale}: invalid coverage record`);
    const glossary = await readJson<{ entries: Record<string, unknown> }>(
      join(localesRoot, locale, "glossary.json"),
    );
    const definitions = await readJson<{ terms: Record<string, string> }>(
      join(localesRoot, "glossary", "terms.json"),
    );
    if (
      !sameValues(
        Object.keys(glossary.entries).sort(),
        Object.keys(definitions.terms).sort(),
      )
    )
      issues.push(`${locale}: glossary term parity failed`);
  }
  for (const overlay of additionalOverlays) {
    if (!existsSync(join(localesRoot, "overlays", `${overlay}.json`)))
      issues.push(`${overlay}: overlay file missing`);
  }
  const context = await readJson<{
    messages: Record<
      string,
      {
        description: string;
        screen: string;
        audience: string;
        tone: string;
        variables: Record<string, string>;
        maxLength: number;
        screenshot: string | null;
        sensitive: boolean;
      }
    >;
  }>(join(localesRoot, "context.json"));
  if (!sameValues(Object.keys(context.messages).sort(), sourceKeys))
    issues.push("context metadata key parity failed");
  for (const key of sourceKeys) {
    const metadata = context.messages[key];
    if (!metadata) continue;
    if (
      !metadata.description ||
      !metadata.screen ||
      !metadata.audience ||
      !metadata.tone ||
      !Number.isInteger(metadata.maxLength) ||
      metadata.maxLength < 1 ||
      typeof metadata.sensitive !== "boolean"
    )
      issues.push(`${key}: incomplete context metadata`);
    if (
      !sameValues(
        Object.keys(metadata.variables).sort(),
        variablesFor(sourceCatalog[key] ?? ""),
      )
    )
      issues.push(`${key}: context placeholder metadata mismatch`);
  }
  const duplicateEnglish = await duplicateObjectKeys(
    join(packageRoot, "src", "en.ts"),
    "en",
  );
  const duplicateGerman = await duplicateObjectKeys(
    join(packageRoot, "src", "de.ts"),
    "de",
  );
  if (duplicateEnglish.length)
    issues.push(`English duplicate keys: ${duplicateEnglish.join(",")}`);
  if (duplicateGerman.length)
    issues.push(`German duplicate keys: ${duplicateGerman.join(",")}`);
  const unknownUsedKeys = (await usedMessageKeys()).filter(
    (key) => !(key in sourceCatalog),
  );
  if (unknownUsedKeys.length)
    issues.push(`Unknown UI message keys: ${unknownUsedKeys.join(",")}`);
  const hardcoded = await hardcodedVisibleStrings();
  if (hardcoded.length)
    issues.push(
      `Hardcoded visible strings (${hardcoded.length}):\n${hardcoded.join("\n")}`,
    );
  if (
    !configuredLocales.includes("en-XA") ||
    !configuredLocales.includes("ar-XB")
  )
    issues.push("pseudo-locales must remain configured");
  if (issues.length)
    throw new Error(
      `Localization validation failed:\n- ${issues.join("\n- ")}`,
    );
  console.log(
    `Validated ${manifest.requiredLocales.length}/36 locale packages, ${sourceKeys.length} keys, ICU placeholders, context, glossaries, BCP 47 metadata, RTL and visible-string extraction.`,
  );
};

const validateRelease = async (): Promise<void> => {
  await validateTechnical();
  const manifest = await readJson<Manifest>(manifestPath);
  const context = await readJson<{
    status: WorkflowStatus;
    messages: Record<
      string,
      { description: string; screenshot: string | null }
    >;
  }>(join(localesRoot, "context.json"));
  const blocked: string[] = [];
  if (context.status !== "in_game_approved")
    blocked.push("shared context metadata is not approved");
  const incompleteContexts = Object.entries(context.messages).filter(
    ([, metadata]) =>
      metadata.description.startsWith("Generated context draft") ||
      !metadata.screenshot ||
      !validEvidencePath(metadata.screenshot),
  );
  if (incompleteContexts.length)
    blocked.push(
      `${incompleteContexts.length} message context records need reviewed screenshots`,
    );
  for (const locale of manifest.requiredLocales) {
    const review = await readJson<LocaleReview>(
      join(localesRoot, locale, "review.json"),
    );
    const coverage = await readJson<LocaleCoverage>(
      join(localesRoot, locale, "coverage.json"),
    );
    const reasons: string[] = [];
    if (review.catalogStatus !== "in_game_approved")
      reasons.push(`catalog=${review.catalogStatus}`);
    if (review.defaultKeyStatus !== "in_game_approved")
      reasons.push(`keys=${review.defaultKeyStatus}`);
    if (
      Object.values(review.keyStatusOverrides).some(
        (status) => status !== "in_game_approved",
      )
    )
      reasons.push("key overrides incomplete");
    if (review.contextStatus !== "in_game_approved")
      reasons.push(`context=${review.contextStatus}`);
    if (review.glossaryStatus !== "in_game_approved")
      reasons.push(`glossary=${review.glossaryStatus}`);
    if (review.accessibility.status !== "in_game_approved")
      reasons.push(`accessibility=${review.accessibility.status}`);
    if (review.screenshots.status !== "in_game_approved")
      reasons.push(`screenshots=${review.screenshots.status}`);
    if (Object.values(review.roles).some((role) => !role))
      reasons.push("roles incomplete");
    const assigned = Object.values(review.roles).filter(
      (role): role is string => Boolean(role),
    );
    if (new Set(assigned).size !== assigned.length)
      reasons.push("independent roles required");
    for (const [approvalName, roleName] of Object.entries(approvalRoles) as [
      ApprovalKind,
      ReviewRole,
    ][]) {
      const approval = review.approvals[approvalName];
      if (!approval) {
        reasons.push(`${approvalName} approval incomplete`);
        continue;
      }
      if (
        !approval.reviewerId.trim() ||
        approval.reviewerId !== review.roles[roleName]
      )
        reasons.push(`${approvalName} reviewer does not match ${roleName}`);
      if (!validIsoTimestamp(approval.approvedAt))
        reasons.push(`${approvalName} timestamp invalid`);
      if (!approval.evidence.length)
        reasons.push(`${approvalName} evidence missing`);
    }
    if (
      ["game", "email", "store", "support", "legal"].some(
        (scope) => coverage.scopes[scope] !== "in_game_approved",
      )
    )
      reasons.push("game/email/store/support/legal coverage incomplete");
    if (
      review.accessibility.status === "in_game_approved" &&
      !review.accessibility.evidence.length
    )
      reasons.push("accessibility evidence missing");
    if (
      review.screenshots.status === "in_game_approved" &&
      review.screenshots.evidence.length < 6
    )
      reasons.push("six screenshot profiles required");
    const evidencePaths = [
      ...review.screenshots.evidence,
      ...review.accessibility.evidence,
      ...Object.values(review.approvals).flatMap((approval) =>
        approval ? approval.evidence : [],
      ),
    ];
    for (const evidence of evidencePaths) {
      if (!validEvidencePath(evidence))
        reasons.push(`missing or external evidence ${evidence}`);
    }
    if (locale !== "en") {
      const catalog = await readLocaleCatalog(locale, manifest.domains);
      if (JSON.stringify(catalog) === JSON.stringify(sourceCatalog))
        reasons.push("source clone detected");
      const identical = Object.keys(sourceCatalog).filter(
        (key) => catalog[key] === sourceCatalog[key],
      );
      const unapprovedIdentical = identical.filter((key) => {
        const approval = review.sourceIdenticalApprovals[key];
        return (
          !approval ||
          !approval.reason.trim() ||
          !approval.reviewerId.trim() ||
          approval.reviewerId !== review.roles.nativeReviewer ||
          !validIsoTimestamp(approval.approvedAt)
        );
      });
      if (unapprovedIdentical.length)
        reasons.push(
          `${unapprovedIdentical.length} source-identical keys lack approval`,
        );
    }
    const glossary = await readJson<{
      status: WorkflowStatus;
      entries: Record<
        string,
        {
          approved: string | null;
          example: string | null;
          status: WorkflowStatus;
        }
      >;
    }>(join(localesRoot, locale, "glossary.json"));
    if (
      glossary.status !== "in_game_approved" ||
      Object.values(glossary.entries).some(
        (entry) =>
          entry.status !== "in_game_approved" ||
          !entry.approved ||
          !entry.example,
      )
    )
      reasons.push("glossary entries incomplete");
    if (reasons.length) blocked.push(`${locale}: ${reasons.join(", ")}`);
  }
  if (blocked.length)
    throw new Error(
      `Global localization release blocked. Human and in-game approvals must never be synthesized:\n- ${blocked.join("\n- ")}`,
    );
  console.log(
    "Global localization release gate passed for 36/36 locales without fallback.",
  );
};

const report = async (): Promise<void> => {
  const manifest = await readJson<Manifest>(manifestPath);
  const rows: string[] = [];
  for (const locale of manifest.requiredLocales) {
    const review = await readJson<LocaleReview>(
      join(localesRoot, locale, "review.json"),
    );
    rows.push(
      `${locale}: catalog=${review.catalogStatus} context=${review.contextStatus} glossary=${review.glossaryStatus} accessibility=${review.accessibility.status} screenshots=${review.screenshots.status}`,
    );
  }
  console.log(rows.join("\n"));
};

const command = process.argv[2] ?? "validate";
if (command === "bootstrap") await bootstrap();
else if (command === "validate" || command === "extract")
  await validateTechnical();
else if (command === "release") await validateRelease();
else if (command === "scan") {
  const hardcoded = await hardcodedVisibleStrings();
  if (hardcoded.length) throw new Error(hardcoded.join("\n"));
  console.log("No hardcoded visible Web or Mobile JSX strings found.");
} else if (command === "pseudo") {
  console.log(
    `Pseudo-locales en-XA and ar-XB generated in memory for ${Object.keys(sourceCatalog).length} keys.`,
  );
} else if (command === "translate") {
  const provider = process.env.TRANSLATION_PROVIDER ?? "disabled";
  if (provider === "disabled")
    console.log(
      "Translation provider disabled; catalogs and review evidence were preserved.",
    );
  else
    console.log(
      `Provider adapter '${provider}' may create machine_draft proposals only; public approval remains a human action.`,
    );
} else if (command === "report") await report();
else throw new Error(`Unknown i18n command: ${command}`);
