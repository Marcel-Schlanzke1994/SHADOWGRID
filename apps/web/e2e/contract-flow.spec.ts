import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const ownCompanyId = "11111111-1111-4111-8111-111111111111";
const externalCompanyId = "22222222-2222-4222-8222-222222222222";
const externalTenderId = "33333333-3333-4333-8333-333333333333";
const ownTenderId = "44444444-4444-4444-8444-444444444444";
const bidId = "55555555-5555-4555-8555-555555555555";

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

const ownCompany = {
  id: ownCompanyId,
  world_id: "world-1",
  founder_profile_id: "profile-1",
  district_id: "district-1",
  industry: "logistics",
  name: "Rhein Provider GmbH",
  status: "private",
  account_balance_cents: 5_000_000,
  enterprise_value_cents: 20_000_000,
  revenue_cents: 2_000_000,
  cost_cents: 1_000_000,
  profit_cents: 1_000_000,
  debt_cents: 0,
  employees: 12,
  capacity: 100,
  quality: 6_000,
  market_share_bps: 1_000,
  reputation_bps: 5_500,
  compliance_bps: 6_000,
  innovation_bps: 5_000,
  risk_bps: 1_000,
  investigation_pressure_bps: 0,
  is_local_simulation: false,
  version: 1,
  created_at: "2026-07-26T08:00:00Z",
  updated_at: "2026-07-26T08:00:00Z",
};

const tender = (
  id: string,
  issuerCompanyId: string,
  issuerCompanyName: string,
  title: string,
) => ({
  id,
  world_id: "world-1",
  issuer_company_id: issuerCompanyId,
  issuer_company_name: issuerCompanyName,
  created_by_profile_id: "profile-2",
  contract_type: "supply",
  title,
  description: "A fictional commercial capacity agreement.",
  max_price_cents: 200_000,
  duration_periods: 2,
  capacity_units: 10,
  min_reputation_bps: 0,
  min_compliance_bps: 0,
  status: "open",
  submission_ends_at: "2026-07-27T14:00:00Z",
  awarded_at: null,
  created_at: "2026-07-27T12:00:00Z",
  bid_count: id === ownTenderId ? 1 : 0,
});

async function mockContractApi(page: Page) {
  let tenders = [
    tender(
      externalTenderId,
      externalCompanyId,
      "Domstadt Handel AG",
      "External logistics supply",
    ),
    tender(ownTenderId, ownCompanyId, ownCompany.name, "Own procurement"),
  ];
  let contracts: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();

    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "contract-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "user-1",
        email: "contracts@example.invalid",
        display_name: "Contract Operator",
        locale: "en",
        email_verified: true,
        is_admin: false,
        is_moderator: false,
      });
      return;
    }
    if (path === "/companies" && method === "GET") {
      await fulfill(route, [ownCompany]);
      return;
    }
    if (path === "/contracts/tenders" && method === "GET") {
      await fulfill(route, tenders);
      return;
    }
    if (path === "/contracts/tenders" && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as Record<string, unknown>;
      const created = {
        ...tender(
          "66666666-6666-4666-8666-666666666666",
          ownCompanyId,
          ownCompany.name,
          String(body.title),
        ),
        ...body,
      };
      tenders = [created, ...tenders];
      await fulfill(route, created, 201);
      return;
    }
    if (
      path === `/contracts/tenders/${externalTenderId}/bids` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as { price_cents: number };
      expect(body.price_cents).toBe(175_000);
      await fulfill(
        route,
        {
          id: "external-bid",
          tender_id: externalTenderId,
          bidder_company_id: ownCompanyId,
          bidder_company_name: ownCompany.name,
          submitted_by_profile_id: "profile-1",
          price_cents: body.price_cents,
          capacity_units: 10,
          score_points: 9_500,
          score_breakdown_json: { price_advantage_bps: 1_250 },
          status: "submitted",
          created_at: "2026-07-27T12:10:00Z",
        },
        201,
      );
      return;
    }
    if (path === `/contracts/tenders/${ownTenderId}/bids` && method === "GET") {
      await fulfill(route, [
        {
          id: bidId,
          tender_id: ownTenderId,
          bidder_company_id: externalCompanyId,
          bidder_company_name: "Domstadt Handel AG",
          submitted_by_profile_id: "profile-2",
          price_cents: 180_000,
          capacity_units: 10,
          score_points: 9_100,
          score_breakdown_json: { price_advantage_bps: 1_000 },
          status: "submitted",
          created_at: "2026-07-27T12:05:00Z",
        },
      ]);
      return;
    }
    if (
      path === `/contracts/tenders/${ownTenderId}/award` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      expect(request.postDataJSON()).toEqual({ bid_id: bidId });
      tenders = tenders.map((item) =>
        item.id === ownTenderId
          ? { ...item, status: "awarded", awarded_at: "2026-07-27T12:15:00Z" }
          : item,
      );
      const awarded = {
        id: "77777777-7777-4777-8777-777777777777",
        world_id: "world-1",
        tender_id: ownTenderId,
        bid_id: bidId,
        issuer_company_id: ownCompanyId,
        issuer_company_name: ownCompany.name,
        provider_company_id: externalCompanyId,
        provider_company_name: "Domstadt Handel AG",
        contract_type: "supply",
        title: "Own procurement",
        price_cents_per_period: 180_000,
        duration_periods: 2,
        periods_settled: 0,
        reserved_capacity_units: 10,
        reputation_reward_bps: 250,
        status: "active",
        starts_at: "2026-07-27T12:15:00Z",
        ends_at: "2026-07-27T14:15:00Z",
        next_settlement_at: "2026-07-27T13:15:00Z",
        completed_at: null,
        breached_at: null,
        breach_reason: null,
        created_at: "2026-07-27T12:15:00Z",
      };
      contracts = [awarded];
      await fulfill(route, awarded, 201);
      return;
    }
    if (path === "/contracts/me") {
      await fulfill(route, contracts);
      return;
    }
    await fulfill(
      route,
      {
        error: {
          code: "e2e.unhandled",
          message: `${method} ${path}`,
        },
        server_time: "2026-07-27T12:00:00Z",
      },
      404,
    );
  });
}

test("player publishes, bids, reviews and awards commercial contracts", async ({
  page,
}) => {
  await mockContractApi(page);
  await page.goto("/contracts");

  await expect(
    page.getByRole("heading", { name: "Commercial contracts" }),
  ).toBeVisible();
  await page.getByLabel("Contract title").fill("New warehouse service");
  await page.getByRole("button", { name: "Publish tender" }).click();
  await expect(page.getByText("Tender published.")).toBeVisible();
  await expect(page.getByText("New warehouse service")).toBeVisible();

  await page.getByLabel("Bid price per period").fill("175000");
  await page.getByRole("button", { name: "Submit bid" }).click();
  await expect(page.getByText("Bid submitted.")).toBeVisible();

  const ownTender = page.locator("article").filter({
    has: page.getByText("Own procurement", { exact: true }),
  });
  await ownTender.getByRole("button", { name: "Review bids" }).click();
  await expect(ownTender.getByText("Domstadt Handel AG")).toBeVisible();
  await ownTender.getByRole("button", { name: "Award contract" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "The provider capacity will be committed.",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Award contract" })
    .click();

  await expect(page.getByText("Contract awarded.")).toBeVisible();
  const history = page.locator(".panel").filter({
    has: page.getByRole("heading", {
      name: "Contracts and settlement history",
    }),
  });
  await expect(history.getByText("Own procurement")).toBeVisible();
  await expect(history.getByText("0 of 2 periods settled")).toBeVisible();
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});
