import i18next from "i18next";
import ICU from "i18next-icu";
import { initReactI18next } from "react-i18next";
import {
  configuredLocales,
  internalSelectableLocales,
  requiredLocales,
  rtlLocales,
  type Locale,
  type RequiredLocale,
} from "@shadowgrid/game-config";
import {
  localeMetadata,
  runtimeApprovedCatalogs,
  runtimeApprovedLocales,
} from "./catalog-loaders.generated";
import { de } from "./de";
import { en } from "./en";

declare const __SHADOWGRID_PRODUCTION__: boolean | undefined;

const expand = (value: string): string =>
  `［${value}］${"～".repeat(Math.max(4, Math.ceil(value.length * 0.3)))}`;
const mirror = (value: string): string => `\u202e${value}\u202c`;
const enXA = Object.fromEntries(
  Object.entries(en).map(([key, value]) => [key, expand(value)]),
);
const arXB = Object.fromEntries(
  Object.entries(en).map(([key, value]) => [key, mirror(value)]),
);
export const isProductionLocaleBuild =
  typeof __SHADOWGRID_PRODUCTION__ !== "undefined"
    ? __SHADOWGRID_PRODUCTION__
    : typeof process !== "undefined" && process.env.NODE_ENV === "production";
const internalRuntimeLocales: readonly Locale[] = isProductionLocaleBuild
  ? []
  : internalSelectableLocales;
const approvedResources = Object.fromEntries(
  Object.entries(runtimeApprovedCatalogs).map(([locale, catalog]) => [
    locale,
    { translation: catalog },
  ]),
);

export const selectableLocales = [
  ...new Set<Locale>([...internalRuntimeLocales, ...runtimeApprovedLocales]),
] as const;

const localeAliases: Readonly<Record<string, Locale>> = {
  "zh-cn": "zh-Hans",
  "zh-sg": "zh-Hans",
  "zh-tw": "zh-Hant",
  "zh-hk": "zh-Hant",
  tl: "fil-PH",
  fa: "fa-IR",
  pt: "pt-BR",
};

export const resolveLocale = (
  requested: string | null | undefined,
  available: readonly Locale[] = selectableLocales,
): Locale => {
  if (!requested) return "en";
  const normalized = requested.replaceAll("_", "-").toLowerCase();
  const exact = available.find((locale) => locale.toLowerCase() === normalized);
  if (exact) return exact;
  const alias = localeAliases[normalized];
  if (alias && available.includes(alias)) return alias;
  const language = normalized.split("-")[0];
  const primary = available.find(
    (locale) =>
      !locale.endsWith("-XA") &&
      !locale.endsWith("-XB") &&
      locale.toLowerCase().split("-")[0] === language,
  );
  return primary ?? "en";
};

export const detectLocale = (): Locale => {
  const stored =
    typeof localStorage === "undefined"
      ? null
      : localStorage.getItem("shadowgrid.locale");
  if (stored) return resolveLocale(stored);
  return resolveLocale(
    typeof navigator === "undefined" ? "en" : navigator.language,
  );
};

export const isRtlLocale = (locale: string): boolean =>
  rtlLocales.has(resolveLocale(locale, configuredLocales));

const applyDocumentLocale = (locale: Locale): void => {
  if (typeof document === "undefined") return;
  document.documentElement.lang = locale;
  document.documentElement.dir = isRtlLocale(locale) ? "rtl" : "ltr";
};

export const i18n = i18next.createInstance();
void i18n
  .use(ICU)
  .use(initReactI18next)
  .init({
    lng: detectLocale(),
    fallbackLng: false,
    supportedLngs: [...selectableLocales],
    nonExplicitSupportedLngs: false,
    interpolation: { escapeValue: false },
    returnEmptyString: false,
    returnNull: false,
    resources: {
      ...approvedResources,
      en: { translation: en },
      ...(isProductionLocaleBuild
        ? {}
        : {
            de: { translation: de },
            "en-XA": { translation: enXA },
            "ar-XB": { translation: arXB },
          }),
    },
  })
  .then(() => applyDocumentLocale(resolveLocale(i18n.language)));

const isRequiredLocale = (locale: Locale): locale is RequiredLocale =>
  requiredLocales.some((candidate) => candidate === locale);

const addApprovedCatalog = async (locale: RequiredLocale): Promise<void> => {
  if (i18n.hasResourceBundle(locale, "translation")) return;
  const catalog = runtimeApprovedCatalogs[locale];
  if (!catalog)
    throw new Error(
      `Locale ${locale} has not passed the in-game approval gate.`,
    );
  i18n.addResourceBundle(locale, "translation", catalog, true, false);
};

export const setLocale = async (requested: Locale): Promise<void> => {
  if (!selectableLocales.includes(requested))
    throw new Error(`Locale ${requested} is not available in this build.`);
  const locale = requested;
  if (isRequiredLocale(locale)) await addApprovedCatalog(locale);
  await i18n.changeLanguage(locale);
  if (typeof localStorage !== "undefined")
    localStorage.setItem("shadowgrid.locale", locale);
  applyDocumentLocale(locale);
};

const intlLocale = (locale: string): string => {
  const resolved = resolveLocale(locale, configuredLocales);
  if (resolved === "en-XA") return "en";
  if (resolved === "ar-XB") return "ar";
  return resolved;
};

export const formatCurrency = (
  value: number,
  locale: string,
  currency = "EUR",
  maximumFractionDigits = 0,
): string =>
  new Intl.NumberFormat(intlLocale(locale), {
    style: "currency",
    currency,
    maximumFractionDigits,
  }).format(value);

export const formatCents = (
  valueCents: number,
  locale: string,
  currency = "EUR",
): string =>
  new Intl.NumberFormat(intlLocale(locale), {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(valueCents / 100);

export const formatNumber = (
  value: number,
  locale: string,
  maximumFractionDigits = 1,
): string =>
  new Intl.NumberFormat(intlLocale(locale), { maximumFractionDigits }).format(
    value,
  );

export const formatPercentFromBasisPoints = (
  basisPoints: number,
  locale: string,
): string =>
  new Intl.NumberFormat(intlLocale(locale), {
    style: "percent",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(basisPoints / 10_000);

export const formatDate = (value: string | Date, locale: string): string =>
  new Intl.DateTimeFormat(intlLocale(locale), {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Berlin",
  }).format(typeof value === "string" ? new Date(value) : value);

export const formatRelativeTime = (
  value: number,
  unit: Intl.RelativeTimeFormatUnit,
  locale: string,
): string =>
  new Intl.RelativeTimeFormat(intlLocale(locale), { numeric: "auto" }).format(
    value,
    unit,
  );

export const bidiIsolate = (value: string): string => `\u2068${value}\u2069`;

export const translateGameValue = (value: string): string =>
  Object.hasOwn(en, value)
    ? i18n.t(value)
    : i18n.t("unknownValue", { value: bidiIsolate(value) });

export {
  configuredLocales,
  requiredLocales,
  rtlLocales,
  runtimeApprovedLocales,
  localeMetadata,
  en,
  de,
};
export type { Locale, RequiredLocale };
