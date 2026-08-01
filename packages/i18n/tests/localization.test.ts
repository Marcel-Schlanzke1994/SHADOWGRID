import assert from "node:assert/strict";
import test from "node:test";
import {
  bidiIsolate,
  configuredLocales,
  formatCents,
  i18n,
  requiredLocales,
  resolveLocale,
  rtlLocales,
  selectableLocales,
  setLocale,
} from "../src/index";

test("the launch manifest exposes exactly 36 primary and seven production RTL locales", () => {
  assert.equal(requiredLocales.length, 36);
  assert.equal(new Set(requiredLocales).size, 36);
  assert.equal(
    [...rtlLocales].filter((locale) => locale !== "ar-XB").length,
    7,
  );
});

test("BCP 47 negotiation handles scripts, regions and internal availability", () => {
  assert.equal(resolveLocale("zh_TW", configuredLocales), "zh-Hant");
  assert.equal(resolveLocale("de-AT", selectableLocales), "de");
  assert.equal(resolveLocale("fa", configuredLocales), "fa-IR");
});

test("money and bidirectional user content are locale-safe", () => {
  assert.notEqual(formatCents(8_000_000, "en"), formatCents(8_000_000, "de"));
  assert.equal(bidiIsolate("Player GmbH"), "\u2068Player GmbH\u2069");
});

test("pseudo-locales preserve ICU variables and unapproved locales cannot be selected", async () => {
  await i18n;
  await setLocale("en-XA");
  const members = i18n.t("members", { count: 2 });
  assert.match(members, /2 members/);
  assert.doesNotMatch(members, /\{count/);
  await assert.rejects(setLocale("es"), /not available/);
  await setLocale("de");
  assert.equal(i18n.t("active"), "Aktiv");
  await setLocale("en");
});
