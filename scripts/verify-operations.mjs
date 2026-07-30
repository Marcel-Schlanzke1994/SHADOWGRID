import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const requiredAlerts = new Set([
  "SHADOWGRID-READINESS",
  "SHADOWGRID-HTTP-5XX",
  "SHADOWGRID-P95-LATENCY",
  "SHADOWGRID-WORKER",
  "SHADOWGRID-REDIS",
  "SHADOWGRID-POSTGRESQL",
  "SHADOWGRID-LEDGER-RECONCILIATION",
]);

const [alertsText, configText, mainText, packageText] = await Promise.all([
  readFile(
    resolve(projectRoot, "monitoring/alert-definitions.json"),
    "utf8",
  ),
  readFile(resolve(projectRoot, "apps/api/shadowgrid/config.py"), "utf8"),
  readFile(resolve(projectRoot, "apps/api/shadowgrid/main.py"), "utf8"),
  readFile(resolve(projectRoot, "package.json"), "utf8"),
]);
const alerts = JSON.parse(alertsText);
const packageJson = JSON.parse(packageText);
if (!Array.isArray(alerts.alerts)) {
  throw new Error("Alert definition must contain an alerts array.");
}
for (const alert of alerts.alerts) {
  if (
    !requiredAlerts.delete(alert.id) ||
    !["critical", "high", "medium"].includes(alert.severity) ||
    !Number.isInteger(alert.evaluation_interval_seconds) ||
    alert.evaluation_interval_seconds < 15 ||
    !alert.owner ||
    !alert.runbook
  ) {
    throw new Error(`Invalid operations alert definition: ${alert.id ?? "unknown"}.`);
  }
}
if (requiredAlerts.size) {
  throw new Error(`Missing alert definitions: ${[...requiredAlerts].join(", ")}.`);
}
if (
  !configText.includes("metrics_token: SecretStr | None") ||
  !mainText.includes('authorization.removeprefix("Bearer ")')
) {
  throw new Error("Production metrics authentication is not configured.");
}
for (const script of [
  "test:season-runbook",
  "smoke:staging:dry-run",
  "smoke:production:dry-run",
  "smoke:staging",
  "smoke:production",
]) {
  if (!packageJson.scripts?.[script]) {
    throw new Error(`Missing operations script: ${script}.`);
  }
}
process.stdout.write(
  `Operations configuration passed: ${alerts.alerts.length} alerts, authenticated production metrics, season and smoke runners.\n`,
);
