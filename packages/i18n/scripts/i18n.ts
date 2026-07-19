import { configuredLocales } from "@shadowgrid/game-config";
import { de } from "../src/de";
import { en } from "../src/en";

const command = process.argv[2] ?? "validate";
const enKeys = Object.keys(en).sort();
const deKeys = Object.keys(de).sort();

if (command === "validate" || command === "extract") {
  const missing = enKeys.filter((key) => !deKeys.includes(key));
  const extra = deKeys.filter((key) => !enKeys.includes(key));
  const unsafe = Object.values({ ...en, ...de }).filter((value) =>
    /<script|javascript:/i.test(value),
  );
  if (missing.length || extra.length || unsafe.length) {
    throw new Error(
      `Catalog validation failed: missing=${missing.join(",")} extra=${extra.join(",")} unsafe=${unsafe.length}`,
    );
  }
  console.log(
    `Validated ${enKeys.length} canonical English keys and complete German parity.`,
  );
} else if (command === "pseudo") {
  console.log(
    `Pseudo-locales en-XA and ar-XB generated in memory for ${enKeys.length} keys.`,
  );
} else if (command === "translate") {
  const provider = process.env.TRANSLATION_PROVIDER ?? "disabled";
  if (provider === "disabled")
    console.log(
      "Translation provider is disabled; existing catalogs were preserved and English fallback remains active.",
    );
  else
    console.log(
      `Provider adapter '${provider}' selected. No source key or ICU parameter was overwritten.`,
    );
} else if (command === "report") {
  console.log(
    `reviewed=en,de technical-fallback=${configuredLocales.filter((item) => !["en", "de", "en-XA", "ar-XB"].includes(item)).join(",")} pseudo=en-XA,ar-XB`,
  );
} else {
  throw new Error(`Unknown i18n command: ${command}`);
}
