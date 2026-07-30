import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const projectRoot = resolve(import.meta.dirname, "..");

function parseArguments(values) {
  return Object.fromEntries(
    values.map((value) => {
      const [key, ...parts] = value.replace(/^--/, "").split("=");
      return [key, parts.length ? parts.join("=") : "true"];
    }),
  );
}

function requireHttpsOutsideLocal(target, baseUrl) {
  const parsed = new URL(baseUrl);
  if (
    target !== "local" &&
    (parsed.protocol !== "https:" ||
      ["localhost", "127.0.0.1", "::1"].includes(parsed.hostname))
  ) {
    throw new Error(`${target} smoke tests require an explicit public HTTPS URL.`);
  }
  return parsed.origin;
}

async function request(baseUrl, path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);
  try {
    return await fetch(`${baseUrl}${path}`, {
      ...options,
      redirect: "error",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function expectJson(response, expectedStatus, label) {
  if (response.status !== expectedStatus) {
    throw new Error(`${label} returned HTTP ${response.status}.`);
  }
  const requestId = response.headers.get("x-request-id");
  const serverTime = response.headers.get("x-server-time");
  if (!requestId || !serverTime) {
    throw new Error(`${label} is missing request tracing headers.`);
  }
  return response.json();
}

function plan(target, baseUrl) {
  return {
    target,
    base_url: baseUrl,
    mode: "dry-run",
    network_requests_sent: false,
    checks: [
      "liveness",
      "readiness",
      "request tracing headers",
      "authenticated session",
      "current account",
      "world list",
      "safe world read",
      "logout",
    ],
    required_secret_environment: ["SMOKE_EMAIL", "SMOKE_PASSWORD"],
  };
}

async function executeSmoke(target, baseUrl) {
  if (
    target === "production" &&
    process.env.FINALIZE_ALLOW_PRODUCTION_DEPLOY !== "true"
  ) {
    throw new Error(
      "Production smoke is blocked until FINALIZE_ALLOW_PRODUCTION_DEPLOY=true.",
    );
  }
  const email = process.env.SMOKE_EMAIL;
  const password = process.env.SMOKE_PASSWORD;
  if (!email || !password) {
    throw new Error("SMOKE_EMAIL and SMOKE_PASSWORD are required.");
  }

  const health = await expectJson(
    await request(baseUrl, "/api/v1/health"),
    200,
    "Liveness",
  );
  if (health.status !== "ok") {
    throw new Error("Liveness payload is not healthy.");
  }
  const ready = await expectJson(
    await request(baseUrl, "/api/v1/ready"),
    200,
    "Readiness",
  );
  if (ready.status !== "ready") {
    throw new Error("Readiness payload is not ready.");
  }

  const login = await request(baseUrl, "/api/v1/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Client-Kind": "mobile",
    },
    body: JSON.stringify({
      email,
      password,
      ...(process.env.SMOKE_TOTP_CODE
        ? { totp_code: process.env.SMOKE_TOTP_CODE }
        : {}),
    }),
  });
  const tokens = await expectJson(login, 200, "Authentication");
  if (typeof tokens.access_token !== "string") {
    throw new Error("Authentication did not return an access token.");
  }
  const authorization = { Authorization: `Bearer ${tokens.access_token}` };
  await expectJson(
    await request(baseUrl, "/api/v1/auth/me", { headers: authorization }),
    200,
    "Current account",
  );
  const worlds = await expectJson(
    await request(baseUrl, "/api/v1/worlds", { headers: authorization }),
    200,
    "World list",
  );
  if (!Array.isArray(worlds) || worlds.length === 0) {
    throw new Error("World list is empty.");
  }
  await expectJson(
    await request(baseUrl, `/api/v1/worlds/${worlds[0].id}/districts`, {
      headers: authorization,
    }),
    200,
    "Safe world read",
  );
  await expectJson(
    await request(baseUrl, "/api/v1/auth/logout", {
      method: "POST",
      headers: authorization,
    }),
    200,
    "Logout",
  );
  return {
    target,
    base_url: baseUrl,
    mode: "live",
    network_requests_sent: true,
    status: "passed",
    checks_passed: 8,
    completed_at: new Date().toISOString(),
  };
}

export async function main(values = process.argv.slice(2)) {
  const args = parseArguments(values);
  const target = args.target ?? "local";
  if (!["local", "staging", "production"].includes(target)) {
    throw new Error("--target must be local, staging or production.");
  }
  const environmentUrl =
    target === "production"
      ? process.env.PRODUCTION_BASE_URL
      : target === "staging"
        ? process.env.STAGING_BASE_URL
        : "http://127.0.0.1:8000";
  const baseUrl = requireHttpsOutsideLocal(
    target,
    args["base-url"] ?? environmentUrl ?? "",
  );
  const result =
    args["dry-run"] === "true"
      ? plan(target, baseUrl)
      : await executeSmoke(target, baseUrl);
  if (args.report) {
    const reportPath = resolve(projectRoot, args.report);
    await mkdir(dirname(reportPath), { recursive: true });
    await writeFile(reportPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  return result;
}

if (
  process.argv[1] &&
  pathToFileURL(resolve(process.argv[1])).href === import.meta.url
) {
  main().catch((error) => {
    process.stderr.write(`Smoke test failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}
