import i18next from "i18next";
import ICU from "i18next-icu";
import { initReactI18next } from "react-i18next";
import {
  configuredLocales,
  rtlLocales,
  type Locale,
} from "@shadowgrid/game-config";
import { en } from "./en";
import { de } from "./de";

const expand = (value: string): string =>
  `［${value.replace(/[aeiou]/gi, (character) => character + character)}］`;
const mirror = (value: string): string => `‮${value}‬`;
const enXA = Object.fromEntries(
  Object.entries(en).map(([key, value]) => [key, expand(value)]),
);
const arXB = Object.fromEntries(
  Object.entries(en).map(([key, value]) => [key, mirror(value)]),
);

export const detectLocale = (): Locale => {
  const stored =
    typeof localStorage === "undefined"
      ? null
      : localStorage.getItem("shadowgrid.locale");
  const browser = typeof navigator === "undefined" ? "en" : navigator.language;
  return (configuredLocales.find((locale) => locale === stored) ??
    configuredLocales.find(
      (locale) => locale.toLowerCase() === browser.toLowerCase(),
    ) ??
    configuredLocales.find((locale) =>
      browser
        .toLowerCase()
        .startsWith(locale.toLowerCase().split("-")[0] ?? locale.toLowerCase()),
    ) ??
    "en") as Locale;
};

export const i18n = i18next.createInstance();
void i18n
  .use(ICU)
  .use(initReactI18next)
  .init({
    lng: detectLocale(),
    fallbackLng: "en",
    supportedLngs: [...configuredLocales],
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    resources: {
      en: { translation: en },
      de: { translation: de },
      "en-XA": { translation: enXA },
      "ar-XB": { translation: arXB },
    },
  });

export const setLocale = async (locale: Locale): Promise<void> => {
  await i18n.changeLanguage(locale);
  localStorage.setItem("shadowgrid.locale", locale);
  document.documentElement.lang = locale;
  document.documentElement.dir = rtlLocales.has(locale) ? "rtl" : "ltr";
};

export { configuredLocales, rtlLocales, en, de };
