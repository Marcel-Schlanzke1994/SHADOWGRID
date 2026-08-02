import { expect, test, type APIResponse } from "@playwright/test";

async function jsonFrom<T>(
  response: APIResponse,
  expectedStatus: number,
): Promise<T> {
  const body = await response.text();
  expect(response.status(), body).toBe(expectedStatus);
  return JSON.parse(body) as T;
}

test("production account can join, found a company and buy property", async ({
  request,
}) => {
  test.skip(
    !process.env.PRODUCTION_BASE_URL ||
      process.env.PRODUCTION_MUTATION_TESTS !== "1",
    "Set PRODUCTION_MUTATION_TESTS=1 to permit the isolated live mutation smoke test.",
  );
  test.setTimeout(120_000);

  const suffix = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const displayName = `Mutation-${suffix}`;
  const password = `Sg!${crypto.randomUUID().replaceAll("-", "")}9a`;

  await jsonFrom<{ message: string }>(
    await request.post("/api/v1/auth/register", {
      data: {
        display_name: displayName,
        password,
        locale: "de",
        terms_accepted: true,
      },
    }),
    201,
  );
  const tokens = await jsonFrom<{ access_token: string }>(
    await request.post("/api/v1/auth/login", {
      data: { display_name: displayName, password },
    }),
    200,
  );
  const authHeaders = { Authorization: `Bearer ${tokens.access_token}` };

  try {
    const worlds = await jsonFrom<Array<{ id: string }>>(
      await request.get("/api/v1/worlds", { headers: authHeaders }),
      200,
    );
    expect(worlds.length).toBeGreaterThan(0);
    const worldId = worlds[0].id;
    const worldHeaders = { ...authHeaders, "x-world-id": worldId };

    const districts = await jsonFrom<Array<{ id: string }>>(
      await request.get(`/api/v1/worlds/${worldId}/districts`, {
        headers: authHeaders,
      }),
      200,
    );
    expect(districts.length).toBeGreaterThan(0);
    const districtId = districts[0].id;

    const profile = await jsonFrom<{ id: string }>(
      await request.post(`/api/v1/worlds/${worldId}/join`, {
        headers: {
          ...authHeaders,
          "Idempotency-Key": `mutation-join-${suffix}`,
        },
        data: {
          codename: `Mutation ${suffix}`,
          archetype: "business_consortium",
          home_district_id: districtId,
        },
      }),
      200,
    );

    const company = await jsonFrom<{
      id: string;
      founder_profile_id: string;
      name: string;
    }>(
      await request.post("/api/v1/companies", {
        headers: {
          ...worldHeaders,
          "Idempotency-Key": `mutation-company-${suffix}`,
        },
        data: {
          name: `Live Werke ${suffix}`,
          industry: "logistics",
          district_id: districtId,
        },
      }),
      201,
    );
    expect(company.founder_profile_id).toBe(profile.id);

    const properties = await jsonFrom<
      Array<{
        id: string;
        listing_type: "sale" | "rent" | null;
        owner_profile_id: string | null;
        effective_sale_price_cents: number;
      }>
    >(
      await request.get("/api/v1/real-estate/properties", {
        headers: worldHeaders,
      }),
      200,
    );
    const property = properties
      .filter(
        (candidate) =>
          candidate.listing_type === "sale" &&
          candidate.owner_profile_id === null,
      )
      .sort(
        (left, right) =>
          left.effective_sale_price_cents - right.effective_sale_price_cents,
      )[0];
    expect(
      property,
      "Production must retain at least one system sale listing",
    ).toBeDefined();

    const transfer = await jsonFrom<{
      property_id: string;
      buyer_profile_id: string;
      transaction_id: string;
    }>(
      await request.post(`/api/v1/real-estate/properties/${property.id}/buy`, {
        headers: {
          ...worldHeaders,
          "Idempotency-Key": `mutation-property-${suffix}`,
        },
      }),
      201,
    );
    expect(transfer.property_id).toBe(property.id);
    expect(transfer.buyer_profile_id).toBe(profile.id);
    expect(transfer.transaction_id).toBeTruthy();

    const companies = await jsonFrom<Array<{ id: string }>>(
      await request.get("/api/v1/companies", { headers: worldHeaders }),
      200,
    );
    expect(companies.some((candidate) => candidate.id === company.id)).toBe(
      true,
    );
    const refreshedProperties = await jsonFrom<
      Array<{ id: string; is_owned_by_me: boolean }>
    >(
      await request.get("/api/v1/real-estate/properties", {
        headers: worldHeaders,
      }),
      200,
    );
    expect(
      refreshedProperties.some(
        (candidate) => candidate.id === property.id && candidate.is_owned_by_me,
      ),
    ).toBe(true);
  } finally {
    await jsonFrom<{ message: string }>(
      await request.delete("/api/v1/privacy/account", {
        headers: authHeaders,
      }),
      200,
    );
  }
});
