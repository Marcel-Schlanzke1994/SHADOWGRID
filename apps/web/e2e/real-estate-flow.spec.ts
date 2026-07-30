import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const companyId = "11111111-1111-4111-8111-111111111111";
const landId = "22222222-2222-4222-8222-222222222222";
const headquartersId = "33333333-3333-4333-8333-333333333333";

const fulfill = async (route: Route, body: unknown, status = 200) => {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
};

const seriousAccessibilityViolations = async (page: Page) =>
  (await new AxeBuilder({ page }).analyze()).violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );

const company = {
  id: companyId,
  world_id: "world-1",
  founder_profile_id: "profile-1",
  district_id: "district-1",
  industry: "technology",
  name: "Rhein Property Systems",
  status: "private",
  account_balance_cents: 2_000_000,
  enterprise_value_cents: 20_000_000,
  revenue_cents: 1_500_000,
  cost_cents: 900_000,
  profit_cents: 600_000,
  debt_cents: 0,
  employees: 10,
  capacity: 100,
  quality: 5_000,
  market_share_bps: 1_000,
  reputation_bps: 5_000,
  compliance_bps: 6_000,
  innovation_bps: 5_000,
  risk_bps: 1_000,
  investigation_pressure_bps: 0,
  is_local_simulation: false,
  version: 1,
  created_at: "2026-07-27T08:00:00Z",
  updated_at: "2026-07-27T08:00:00Z",
};

const property = (
  id: string,
  propertyType: "land" | "headquarters",
  name: string,
  owned: boolean,
) => ({
  id,
  world_id: "world-1",
  city_id: "city-1",
  city_name: "Cologne",
  district_id: "district-1",
  district_name: "Innenstadt",
  property_code: `innenstadt-${propertyType}-01`,
  property_type: propertyType,
  name,
  area_units: propertyType === "land" ? 100 : 60,
  base_value_cents: propertyType === "land" ? 1_000_000 : 3_000_000,
  improvement_value_cents: 0,
  owner_profile_id: owned ? "profile-1" : null,
  owner_name: owned ? "Property Operator" : null,
  is_owned_by_me: owned,
  company_use_id: owned ? companyId : null,
  company_use_name: owned ? company.name : null,
  status: owned ? "owned" : "available",
  listing_type: owned ? null : "sale",
  asking_price_cents: propertyType === "land" ? 1_000_000 : 3_000_000,
  rent_cents_per_period: 0,
  effective_sale_price_cents:
    propertyType === "land" ? 1_100_000 : 3_300_000,
  effective_rent_cents_per_period: 0,
  headquarters_level: 0,
  version: 1,
  created_at: "2026-07-27T08:00:00Z",
  updated_at: "2026-07-27T08:00:00Z",
});

async function mockRealEstateApi(page: Page) {
  let properties = [
    property(landId, "land", "Innenstadt Development parcel", false),
    property(
      headquartersId,
      "headquarters",
      "Innenstadt Headquarters property",
      true,
    ),
  ];
  let leases: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "property-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "user-1",
        email: "property@example.invalid",
        display_name: "Property Operator",
        locale: "en",
        email_verified: true,
        is_admin: false,
        is_moderator: false,
      });
      return;
    }
    if (path === "/companies" && method === "GET") {
      await fulfill(route, [company]);
      return;
    }
    if (path === "/real-estate/config") {
      await fulfill(route, {
        index_interval_minutes: 1_440,
        lease_interval_minutes: 1_440,
        max_lease_periods: 30,
        headquarters_upgrade_base_cost_cents: 500_000,
      });
      return;
    }
    if (path === "/real-estate/indices") {
      await fulfill(route, [
        {
          id: "index-1",
          world_id: "world-1",
          city_id: "city-1",
          city_name: "Cologne",
          district_id: "district-1",
          district_name: "Innenstadt",
          price_index_bps: 11_000,
          rent_index_bps: 10_500,
          demand_bps: 12_000,
          safety_score: 70,
          infrastructure_score: 85,
          economic_score: 90,
          cartel_control_points: 0,
          event_multiplier_bps: 10_000,
          version: 1,
          updated_at: "2026-07-27T08:00:00Z",
        },
      ]);
      return;
    }
    if (path === "/real-estate/properties" && method === "GET") {
      await fulfill(route, properties);
      return;
    }
    if (path === "/real-estate/leases/me") {
      await fulfill(route, leases);
      return;
    }
    if (path === `/real-estate/properties/${landId}/buy` && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      properties = properties.map((item) =>
        item.id === landId
          ? {
              ...item,
              owner_profile_id: "profile-1",
              owner_name: "Property Operator",
              is_owned_by_me: true,
              status: "owned",
              listing_type: null,
              company_use_id: null,
              company_use_name: null,
              version: 2,
            }
          : item,
      );
      await fulfill(
        route,
        {
          id: "transfer-1",
          property_id: landId,
          seller_profile_id: null,
          buyer_profile_id: "profile-1",
          price_cents: 1_100_000,
          price_index_bps: 11_000,
          transfer_type: "system_sale",
          transaction_id: "transaction-1",
          created_at: "2026-07-27T09:00:00Z",
        },
        201,
      );
      return;
    }
    if (
      path === `/real-estate/properties/${landId}/list-rent` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      expect(request.postDataJSON()).toEqual({
        rent_cents_per_period: 100_000,
      });
      properties = properties.map((item) =>
        item.id === landId
          ? {
              ...item,
              listing_type: "rent",
              rent_cents_per_period: 100_000,
              effective_rent_cents_per_period: 105_000,
              version: 3,
            }
          : item,
      );
      await fulfill(
        route,
        properties.find((item) => item.id === landId),
      );
      return;
    }
    if (
      path === `/real-estate/properties/${landId}/lease` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      expect(request.postDataJSON()).toEqual({
        tenant_company_id: companyId,
        term_periods: 2,
      });
      properties = properties.map((item) =>
        item.id === landId
          ? {
              ...item,
              status: "leased",
              listing_type: null,
              company_use_id: companyId,
              company_use_name: company.name,
              version: 4,
            }
          : item,
      );
      const lease = {
        id: "lease-1",
        world_id: "world-1",
        property_id: landId,
        property_name: "Innenstadt Development parcel",
        landlord_profile_id: "profile-1",
        landlord_name: "Property Operator",
        tenant_company_id: companyId,
        tenant_company_name: company.name,
        rent_cents_per_period: 105_000,
        term_periods: 2,
        periods_paid: 1,
        status: "active",
        default_reason: null,
        starts_at: "2026-07-27T09:05:00Z",
        ends_at: "2026-07-29T09:05:00Z",
        next_payment_at: "2026-07-28T09:05:00Z",
        completed_at: null,
        defaulted_at: null,
        cancelled_at: null,
        created_at: "2026-07-27T09:05:00Z",
        payments: [
          {
            id: "payment-1",
            period_number: 1,
            amount_cents: 105_000,
            status: "paid",
            transaction_id: "transaction-2",
            input_snapshot_json: { rent_index_bps: 10_500 },
            paid_at: "2026-07-27T09:05:00Z",
          },
        ],
      };
      leases = [lease];
      await fulfill(route, lease, 201);
      return;
    }
    if (
      path ===
        `/real-estate/properties/${headquartersId}/headquarters/upgrade` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      properties = properties.map((item) =>
        item.id === headquartersId
          ? { ...item, headquarters_level: 1, version: 2 }
          : item,
      );
      await fulfill(
        route,
        {
          id: "improvement-1",
          property_id: headquartersId,
          company_id: companyId,
          improvement_type: "headquarters_upgrade",
          level_after: 1,
          cost_cents: 550_000,
          transaction_id: "transaction-3",
          created_at: "2026-07-27T09:10:00Z",
        },
        201,
      );
      return;
    }
    await fulfill(
      route,
      {
        error: { code: "e2e.unhandled", message: `${method} ${path}` },
        server_time: "2026-07-27T09:00:00Z",
      },
      404,
    );
  });
}

test("player buys, lists and leases property, then upgrades headquarters", async ({
  page,
}) => {
  await mockRealEstateApi(page);
  await page.goto("/real-estate");

  await expect(
    page.getByRole("heading", { name: "Real estate and headquarters" }),
  ).toBeVisible();
  const landCard = page.locator("article").filter({
    has: page.getByText("Innenstadt Development parcel"),
  });
  await landCard.getByRole("button", { name: "Review purchase" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "immutable ledger",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Buy property" })
    .click();
  await expect(
    page.getByText("Property purchased through the balanced ledger."),
  ).toBeVisible();

  await page.getByLabel("Listing type").selectOption("rent");
  await page.getByLabel("Base amount in cents").fill("100000");
  await page.getByRole("button", { name: "Publish listing" }).click();
  await expect(page.getByText("Property listing published.")).toBeVisible();

  await page.getByRole("button", { name: "Review lease" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "The first rent is due now.",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Start lease" })
    .click();
  await expect(
    page.getByText("Company lease started and first rent posted."),
  ).toBeVisible();
  await expect(page.getByText("1 of 2 rent periods paid")).toBeVisible();

  await page
    .getByRole("button", { name: "Review headquarters upgrade" })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "assigned company account",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Upgrade headquarters" })
    .click();
  await expect(
    page.getByText("Headquarters upgraded through the company ledger."),
  ).toBeVisible();
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});
