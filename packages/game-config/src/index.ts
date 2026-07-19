export const organizationArchetypes = ["family_network", "street_alliance", "business_consortium", "cyber_collective"] as const;
export const businessTypes = ["gastronomy", "event_agency", "security_company", "logistics_company", "technology_company"] as const;
export const specialistRoles = ["strategist", "finance_director", "district_coordinator", "intelligence_analyst", "negotiator", "security_manager", "personnel_manager", "technology_expert"] as const;
export const operationTypes = ["business_expansion", "intelligence_gathering", "influence_project", "diplomatic_mission", "covert_market_project"] as const;
export const configuredLocales = ["en", "de", "fr", "es", "it", "pt-BR", "pt-PT", "nl", "pl", "cs", "sk", "hu", "ro", "bg", "el", "tr", "ru", "uk", "ar", "he", "fa", "ur", "hi", "bn", "ta", "te", "th", "vi", "id", "ms", "zh-CN", "zh-TW", "ja", "ko", "sv", "no", "da", "fi", "et", "lv", "lt", "sl", "hr", "sr", "sw", "af", "en-XA", "ar-XB"] as const;
export type Locale = typeof configuredLocales[number];
export const rtlLocales = new Set<Locale>(["ar", "he", "fa", "ur", "ar-XB"]);
