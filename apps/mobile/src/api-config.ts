const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

export function resolveApiBaseUrl(
  configuredUrl: string | undefined,
  fallbackUrl: string | undefined,
  environment: string | undefined,
): string {
  const value =
    configuredUrl ?? fallbackUrl ?? "http://localhost:8000/api/v1";
  const parsed = new URL(value);
  const normalizedEnvironment = (environment ?? "development").toLowerCase();
  if (
    ["production", "staging"].includes(normalizedEnvironment) &&
    (parsed.protocol !== "https:" || LOCAL_HOSTS.has(parsed.hostname))
  ) {
    throw new Error(
      "Public mobile builds require an explicit non-local HTTPS API URL.",
    );
  }
  if (!parsed.pathname.endsWith("/api/v1")) {
    throw new Error("Mobile API URL must end with /api/v1.");
  }
  parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  return parsed.toString().replace(/\/$/, "");
}
