import { expect, test } from "@playwright/test";

const publicRoutes = [
  "/",
  "/login",
  "/register",
  "/forgot-password",
  "/verify-email",
  "/reset-password",
] as const;

const protectedRoutes = [
  "/worlds",
  "/tutorial",
  "/command",
  "/engagement",
  "/legacy",
  "/city",
  "/germany",
  "/companies",
  "/exchange",
  "/businesses",
  "/facilities",
  "/specialists",
  "/operations",
  "/network",
  "/intelligence",
  "/investigation",
  "/cartels",
  "/organizations",
  "/diplomacy",
  "/pvp",
  "/territories",
  "/wars",
  "/alliances",
  "/communications",
  "/market",
  "/contracts",
  "/finance",
  "/bonds",
  "/real-estate",
  "/research",
  "/news",
  "/rankings",
  "/settings",
  "/admin",
  "/moderation",
] as const;

const placeholderId = "00000000-0000-0000-0000-000000000000";

test("production routes and authenticated GET operations avoid unhandled failures", async ({
  page,
  request,
}) => {
  test.skip(
    !process.env.PRODUCTION_BASE_URL,
    "This acceptance matrix is reserved for the deployed alpha environment.",
  );
  test.setTimeout(240_000);

  const suffix = crypto.randomUUID().replaceAll("-", "").slice(0, 10);
  const displayName = `RouteMatrix-${suffix}`;
  const password = `Sg!${crypto.randomUUID().replaceAll("-", "")}9a`;
  const pageErrors: string[] = [];
  const serverErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("response", (response) => {
    if (response.url().includes("/api/v1/") && response.status() >= 500) {
      serverErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto("/register");
  await page.locator('input[name="displayName"]').fill(displayName);
  await page.locator('input[name="password"]').fill(password);
  const loginResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/login") &&
      response.request().method() === "POST",
  );
  await page.locator('button[type="submit"]').click();
  const loginResponse = await loginResponsePromise;
  expect(loginResponse.ok()).toBeTruthy();
  const tokens = (await loginResponse.json()) as { access_token: string };
  const authHeaders = { Authorization: `Bearer ${tokens.access_token}` };

  try {
    const worldsResponse = await request.get("/api/v1/worlds", {
      headers: authHeaders,
    });
    expect(worldsResponse.ok()).toBeTruthy();
    const worlds = (await worldsResponse.json()) as Array<{ id: string }>;
    expect(worlds.length).toBeGreaterThan(0);
    const worldId = worlds[0].id;

    const districtsResponse = await request.get(
      `/api/v1/worlds/${worldId}/districts`,
      { headers: authHeaders },
    );
    expect(districtsResponse.ok()).toBeTruthy();
    const districts = (await districtsResponse.json()) as Array<{
      id: string;
      city_id?: string | null;
    }>;
    expect(districts.length).toBeGreaterThan(0);
    const districtId = districts[0].id;
    const cityId = districts[0].city_id ?? placeholderId;

    const joinResponse = await request.post(`/api/v1/worlds/${worldId}/join`, {
      headers: {
        ...authHeaders,
        "Idempotency-Key": `route-matrix-${suffix}`,
      },
      data: {
        codename: `Matrix ${suffix}`,
        archetype: "business_consortium",
        home_district_id: districtId,
      },
    });
    expect(joinResponse.ok()).toBeTruthy();
    const profile = (await joinResponse.json()) as { id: string };

    const concreteRoutes = [
      ...protectedRoutes,
      `/city/${districtId}`,
      `/companies/${placeholderId}`,
      `/exchange/${placeholderId}`,
      `/businesses/${placeholderId}`,
      `/specialists/${placeholderId}`,
      `/operations/${placeholderId}`,
      `/cartels/${placeholderId}`,
      "/organizations/overview",
    ];
    for (const viewport of [
      { width: 1440, height: 1000 },
      { width: 412, height: 915 },
    ]) {
      await page.setViewportSize(viewport);
      for (const route of concreteRoutes) {
        await page.goto(route, { waitUntil: "domcontentloaded" });
        await expect(page.locator("body")).toBeVisible();
        await page.waitForTimeout(150);
      }
    }

    const openApiResponse = await request.get("/api/v1/openapi.json");
    expect(openApiResponse.ok()).toBeTruthy();
    const openApi = (await openApiResponse.json()) as {
      paths: Record<string, Record<string, unknown>>;
    };
    const idValues: Record<string, string> = {
      world_id: worldId,
      district_id: districtId,
      city_id: cityId,
      profile_id: profile.id,
    };
    const getFailures: string[] = [];
    let getCount = 0;
    for (const [path, operations] of Object.entries(openApi.paths)) {
      if (!("get" in operations)) continue;
      getCount += 1;
      const concretePath = path.replaceAll(
        /\{([^}]+)\}/g,
        (_match, parameter: string) => idValues[parameter] ?? placeholderId,
      );
      const response = await request.get(concretePath, {
        headers: authHeaders,
      });
      if (response.status() >= 500) {
        getFailures.push(`${response.status()} ${concretePath}`);
      }
    }
    expect(getCount).toBeGreaterThan(150);
    expect(getFailures).toEqual([]);

    for (const route of publicRoutes) {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await expect(page.locator("body")).toBeVisible();
    }
    expect(pageErrors).toEqual([]);
    expect(serverErrors).toEqual([]);
  } finally {
    const cleanup = await request.delete("/api/v1/privacy/account", {
      headers: authHeaders,
    });
    expect(cleanup.ok()).toBeTruthy();
  }
});
