import { readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const mobileRoot = resolve(projectRoot, "apps/mobile");
const [appText, easText, packageText] = await Promise.all([
  readFile(resolve(mobileRoot, "app.json"), "utf8"),
  readFile(resolve(mobileRoot, "eas.json"), "utf8"),
  readFile(resolve(mobileRoot, "package.json"), "utf8"),
]);
const app = JSON.parse(appText).expo;
const eas = JSON.parse(easText);
const packageJson = JSON.parse(packageText);
const identifier = "game.shadowgrid.mobile";
if (
  app.ios?.bundleIdentifier !== identifier ||
  app.android?.package !== identifier
) {
  throw new Error("Android and iOS bundle identifiers must match the reviewed identifier.");
}
if (
  appText.includes("00000000-0000-0000-0000-000000000000") ||
  appText.includes(".example") ||
  easText.includes(".example")
) {
  throw new Error("Mobile configuration contains a placeholder project or domain.");
}
const productionUrl = eas.build?.production?.env?.EXPO_PUBLIC_API_URL;
const parsedProductionUrl = new URL(productionUrl);
if (
  parsedProductionUrl.protocol !== "https:" ||
  !parsedProductionUrl.pathname.endsWith("/api/v1")
) {
  throw new Error("Production mobile API URL must be HTTPS and end with /api/v1.");
}
if (
  eas.build?.production?.env?.EXPO_PUBLIC_APP_ENV !== "production" ||
  !packageJson.scripts?.["build:preview"]
) {
  throw new Error("Mobile production environment or preview export is incomplete.");
}
for (const file of await readdir(mobileRoot, { recursive: true })) {
  if (/\.(jks|keystore|p8|p12|mobileprovision)$/i.test(file)) {
    throw new Error(`Signing material must not be committed: ${file}.`);
  }
}
for (const path of [
  "store/metadata.de-DE.md",
  "store/metadata.en-US.md",
  "store/data-safety.md",
]) {
  await readFile(resolve(mobileRoot, path), "utf8");
}
process.stdout.write(
  "Mobile release configuration passed: identifiers, HTTPS API, store drafts, preview export and credential hygiene.\n",
);
