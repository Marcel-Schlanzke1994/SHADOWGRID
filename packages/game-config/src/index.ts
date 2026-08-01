export const organizationArchetypes = [
  "family_network",
  "street_alliance",
  "business_consortium",
  "cyber_collective",
] as const;
export const businessTypes = [
  "gastronomy",
  "event_agency",
  "security_company",
  "logistics_company",
  "technology_company",
] as const;
export const companyIndustries = [
  "gastronomy",
  "logistics",
  "technology",
] as const;
export const companyInvestmentTypes = [
  "capacity",
  "quality",
  "innovation",
  "compliance",
] as const;
export const specialistRoles = [
  "finance_director",
  "technology_expert",
  "market_analyst",
  "compliance_officer",
  "logistics_expert",
  "diplomat",
] as const;
export const operationTypes = [
  "business_expansion",
  "intelligence_gathering",
  "influence_project",
  "diplomatic_mission",
  "covert_market_project",
] as const;
export const requiredLocales = [
  "en",
  "zh-Hans",
  "es",
  "hi",
  "fr",
  "ar",
  "bn",
  "pt-BR",
  "id",
  "ur",
  "ru",
  "de",
  "ja",
  "pcm",
  "arz",
  "mr",
  "vi",
  "te",
  "sw",
  "ha",
  "tr",
  "pnb",
  "fil-PH",
  "ta",
  "yue-Hant",
  "wuu-Hans",
  "fa-IR",
  "ko",
  "am",
  "th",
  "jv",
  "it",
  "gu",
  "kn",
  "apc",
  "apd",
] as const;

export const regionalOverlayLocales = [
  "en-US",
  "en-GB",
  "es-ES",
  "es-419",
  "pt-PT",
  "fr-FR",
  "fr-CA",
  "de-DE",
  "de-AT",
  "de-CH",
  "zh-Hant",
] as const;

export const pseudoLocales = [
  "en-XA",
  "ar-XB",
] as const;

export const configuredLocales = [
  ...requiredLocales,
  ...regionalOverlayLocales,
  ...pseudoLocales,
] as const;
export type Locale = (typeof configuredLocales)[number];
export type RequiredLocale = (typeof requiredLocales)[number];
export type RegionalOverlayLocale = (typeof regionalOverlayLocales)[number];
export const internalSelectableLocales = ["en", "de", ...pseudoLocales] as const;
export const rtlLocales = new Set<Locale>([
  "ar",
  "arz",
  "ur",
  "pnb",
  "fa-IR",
  "apc",
  "apd",
  "ar-XB",
]);
