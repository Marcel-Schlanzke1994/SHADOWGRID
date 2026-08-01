import { resolveApiBaseUrl } from "./api-config";

describe("mobile API configuration", () => {
  it("uses the local fallback only in development", () => {
    expect(resolveApiBaseUrl(undefined, undefined, "development")).toBe(
      "http://localhost:8000/api/v1",
    );
  });

  it("accepts the verified public production API contract", () => {
    expect(
      resolveApiBaseUrl(
        "https://shadowgrid-production-be34.up.railway.app/api/v1",
        undefined,
        "production",
      ),
    ).toBe("https://shadowgrid-production-be34.up.railway.app/api/v1");
  });

  it.each([
    "http://shadowgrid.example/api/v1",
    "https://localhost:8000/api/v1",
    "https://127.0.0.1/api/v1",
  ])("rejects an unsafe public URL: %s", (url) => {
    expect(() => resolveApiBaseUrl(url, undefined, "production")).toThrow(
      "explicit non-local HTTPS",
    );
  });

  it("rejects an endpoint outside the versioned API root", () => {
    expect(() =>
      resolveApiBaseUrl(
        "https://shadowgrid.example/api",
        undefined,
        "production",
      ),
    ).toThrow("must end with /api/v1");
  });
});
