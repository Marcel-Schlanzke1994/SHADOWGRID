import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const companyId = "11111111-1111-4111-8111-111111111111";
const competitorCompanyId = "44444444-4444-4444-8444-444444444444";
const competitorListingId = "22222222-2222-4222-8222-222222222222";
const ownListingId = "33333333-3333-4333-8333-333333333333";
const shareClassId = "55555555-5555-4555-8555-555555555555";

const privateCompany = {
  id: companyId,
  world_id: "world-1",
  founder_profile_id: "profile-1",
  district_id: "district-1",
  industry: "logistics",
  name: "RheinCargo Solutions",
  status: "private",
  account_balance_cents: 4_000_000,
  enterprise_value_cents: 20_000_000,
  revenue_cents: 3_500_000,
  cost_cents: 2_700_000,
  profit_cents: 800_000,
  debt_cents: 0,
  employees: 8,
  capacity: 3_000,
  quality: 5_000,
  market_share_bps: 1_200,
  reputation_bps: 4_800,
  compliance_bps: 6_000,
  innovation_bps: 4_200,
  risk_bps: 1_800,
  investigation_pressure_bps: 0,
  is_local_simulation: false,
  version: 4,
  created_at: "2026-07-26T08:00:00Z",
  updated_at: "2026-07-26T12:00:00Z",
};

const competitorListing = {
  id: competitorListingId,
  world_id: "world-1",
  company_id: competitorCompanyId,
  company_name: "Domlinie Logistik",
  company_industry: "logistics",
  symbol: "DOML",
  status: "active",
  total_shares: 100_000,
  offered_shares: 3_000,
  initial_price_cents: 200,
  last_price_cents: 205,
  enterprise_value_cents: 20_500_000,
  profit_cents: 810_000,
  debt_cents: 0,
  ipo_fee_cents: 500_000,
  listed_at: "2026-07-26T10:00:00Z",
  updated_at: "2026-07-26T12:00:00Z",
};

const ownListing = {
  ...competitorListing,
  id: ownListingId,
  company_id: companyId,
  company_name: privateCompany.name,
  symbol: "RCS",
  offered_shares: 20_000,
  last_price_cents: 200,
  enterprise_value_cents: 20_000_000,
};

const economyReport = {
  id: "report-1",
  tick_id: "tick-1",
  market_report_id: "market-report-1",
  company_id: competitorCompanyId,
  settlement_transaction_id: "transaction-1",
  attractiveness_points: 42_000,
  allocated_units: 3_000,
  market_share_bps: 3_000,
  revenue_cents: 3_501_000,
  cost_cents: 2_700_000,
  profit_cents: 801_000,
  cash_delta_cents: 801_000,
  debt_delta_cents: 0,
  enterprise_value_before_cents: 20_000_000,
  enterprise_value_after_cents: 20_801_000,
  inputs_json: { capacity_units: 3_000 },
  modifiers_json: { quality: 20_000 },
  created_at: "2026-07-26T13:00:01Z",
};

const fulfill = async (route: Route, body: unknown, status = 200) => {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
};

async function mockExchangeApi(page: Page) {
  let company = { ...privateCompany };
  let listings = [{ ...competitorListing }];
  let orders: Array<Record<string, unknown>> = [];
  let dividends: Array<Record<string, unknown>> = [];

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();

    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "e2e-exchange-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "e2e-user",
        email: "player@example.invalid",
        display_name: "E2E Trader",
        locale: "en",
      });
      return;
    }
    if (path === "/exchange/config") {
      await fulfill(route, {
        min_enterprise_value_cents: 10_000_000,
        profitable_periods: 3,
        min_compliance_bps: 6_000,
        min_employees: 8,
        max_investigation_pressure_bps: 2_500,
        ipo_fee_cents: 500_000,
        order_rate_limit_per_minute: 60,
        max_price_deviation_bps: 5_000,
      });
      return;
    }
    if (path === "/companies" && method === "GET") {
      await fulfill(route, [company]);
      return;
    }
    if (path === `/companies/${companyId}/ipo-eligibility`) {
      await fulfill(route, {
        eligible: true,
        reasons: [],
        metrics: {
          enterprise_value_cents: 20_000_000,
          profitable_periods: 3,
          audited_reports: 3,
          compliance_bps: 6_000,
          employees: 8,
          investigation_pressure_bps: 0,
          available_company_cash_cents: 4_000_000,
        },
      });
      return;
    }
    if (path === `/companies/${companyId}/ipo` && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      expect(request.postDataJSON()).toEqual({
        symbol: "RCS",
        total_shares: 100_000,
        offered_shares: 20_000,
      });
      company = { ...company, status: "public" };
      listings = [...listings, { ...ownListing }];
      await fulfill(route, ownListing, 201);
      return;
    }
    if (path === "/exchange/listings") {
      await fulfill(route, listings);
      return;
    }
    if (path === "/exchange/orders/me") {
      await fulfill(route, orders);
      return;
    }
    if (path === "/exchange/portfolio") {
      await fulfill(route, [
        {
          holding_id: "holding-1",
          listing_id: competitorListingId,
          company_id: competitorCompanyId,
          company_name: competitorListing.company_name,
          symbol: competitorListing.symbol,
          share_class: "common",
          quantity: 250,
          reserved_quantity: 0,
          available_quantity: 250,
          average_cost_cents: 200,
          last_price_cents: 205,
          market_value_cents: 51_250,
          voting_rights: 250,
        },
      ]);
      return;
    }
    if (path === "/exchange/orders" && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      expect(request.postDataJSON()).toMatchObject({
        listing_id: ownListingId,
        side: "buy",
        order_type: "limit",
        quantity: 10,
        limit_price_cents: 200,
      });
      const order = {
        id: "order-1",
        listing_id: ownListingId,
        share_class_id: shareClassId,
        side: "buy",
        order_type: "limit",
        limit_price_cents: 200,
        original_quantity: 10,
        remaining_quantity: 10,
        reserved_cash_cents: 2_000,
        reserved_shares: 0,
        status: "open",
        expires_at: null,
        created_at: "2026-07-26T14:00:00Z",
        updated_at: "2026-07-26T14:00:00Z",
      };
      orders = [order];
      await fulfill(route, order, 201);
      return;
    }
    if (path === "/exchange/orders/order-1" && method === "DELETE") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      orders = orders.map((order) => ({
        ...order,
        status: "cancelled",
        reserved_cash_cents: 0,
      }));
      await fulfill(route, orders[0]);
      return;
    }
    if (path === `/companies/${companyId}/dividends` && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      expect(request.postDataJSON()).toEqual({ per_share_cents: 2 });
      const dividend = {
        id: "dividend-1",
        listing_id: ownListingId,
        share_class_id: shareClassId,
        declared_by_profile_id: "profile-1",
        per_share_cents: 2,
        total_paid_cents: 160_000,
        eligible_shares: 80_000,
        status: "paid",
        snapshot_at: "2026-07-26T15:00:00Z",
        paid_at: "2026-07-26T15:00:00Z",
        created_at: "2026-07-26T15:00:00Z",
      };
      dividends = [dividend];
      await fulfill(route, dividend, 201);
      return;
    }

    const detailMatch = path.match(
      /^\/exchange\/listings\/([^/]+)\/(order-book|trades|prices|reports|shareholders|dividends)$/,
    );
    if (detailMatch) {
      const [, currentListingId, resource] = detailMatch;
      if (resource === "order-book") {
        await fulfill(route, {
          buys: [],
          sells: [
            {
              id: "ipo-order-1",
              listing_id: currentListingId,
              share_class_id: shareClassId,
              side: "sell",
              order_type: "ipo",
              limit_price_cents: 200,
              original_quantity: 20_000,
              remaining_quantity: 20_000,
              reserved_cash_cents: 0,
              reserved_shares: 20_000,
              status: "open",
              expires_at: null,
              created_at: "2026-07-26T10:00:00Z",
              updated_at: "2026-07-26T10:00:00Z",
            },
          ],
        });
        return;
      }
      if (resource === "trades") {
        await fulfill(route, [
          {
            id: "trade-1",
            listing_id: currentListingId,
            share_class_id: shareClassId,
            buy_order_id: "buy-1",
            sell_order_id: "sell-1",
            buyer_profile_id: "profile-2",
            seller_profile_id: null,
            seller_company_id: competitorCompanyId,
            quantity: 250,
            price_cents: 205,
            gross_cents: 51_250,
            executed_at: "2026-07-26T12:00:00Z",
          },
        ]);
        return;
      }
      if (resource === "prices") {
        await fulfill(route, [
          {
            id: "price-1",
            listing_id: currentListingId,
            trade_id: "trade-1",
            price_cents: 205,
            volume: 250,
            captured_at: "2026-07-26T12:00:00Z",
          },
        ]);
        return;
      }
      if (resource === "reports") {
        await fulfill(route, [
          {
            ...economyReport,
            company_id:
              currentListingId === ownListingId
                ? companyId
                : competitorCompanyId,
          },
        ]);
        return;
      }
      if (resource === "shareholders") {
        await fulfill(route, [
          {
            holding_id: "holding-founder",
            profile_id: "profile-1",
            codename: "E2E Trader",
            quantity: 80_000,
            ownership_bps: 8_000,
            voting_rights: 80_000,
          },
        ]);
        return;
      }
      if (resource === "dividends") {
        await fulfill(
          route,
          currentListingId === ownListingId ? dividends : [],
        );
        return;
      }
    }
    await route.abort();
  });
}

test("IPO, order lifecycle and dividend flow are explicit and accessible", async ({
  page,
}) => {
  await mockExchangeApi(page);
  await page.goto("/exchange");

  await expect(
    page.getByRole("heading", { level: 1, name: "Stock exchange" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 3, name: "Domlinie Logistik" }),
  ).toBeVisible();
  await page.getByLabel("Symbol").fill("RCS");
  await page.getByLabel("Total shares").fill("100000");
  await page.getByLabel("Offered shares").fill("20000");
  await page.getByRole("button", { name: "Start IPO" }).click();

  const ipoDialog = page.getByRole("dialog");
  await expect(ipoDialog).toContainText("€5,000.00");
  await ipoDialog.getByRole("button", { name: "Start IPO" }).click();
  await expect(
    page.getByText(
      "The company was listed and its fixed share supply was issued.",
    ),
  ).toBeVisible();
  await page.getByRole("link", { name: /RCS RheinCargo Solutions/ }).click();
  await expect(page).toHaveURL(new RegExp(`/exchange/${ownListingId}$`));
  await expect(
    page.getByRole("region", { name: "RheinCargo Solutions" }),
  ).toBeVisible();

  await page.getByLabel("Quantity").fill("10");
  await page.getByLabel("Limit price in cents").fill("200");
  await page.getByRole("button", { name: "Review order" }).click();
  const orderDialog = page.getByRole("dialog");
  await expect(orderDialog).toContainText("€20.00");
  await orderDialog.getByRole("button", { name: "Place order" }).click();
  await expect(
    page.getByText(
      "The order was accepted and matched atomically where possible.",
    ),
  ).toBeVisible();

  await page.getByRole("button", { name: "Cancel order" }).click();
  const cancelDialog = page.getByRole("dialog");
  await cancelDialog.getByRole("button", { name: "Cancel order" }).click();
  await expect(
    page.getByText("The open order and its reservations were cancelled."),
  ).toBeVisible();

  await page.getByLabel("Dividend per share in cents").fill("2");
  await page.getByRole("button", { name: "Review dividend" }).click();
  const dividendDialog = page.getByRole("dialog");
  await expect(dividendDialog).toContainText("€0.02");
  await dividendDialog.getByRole("button", { name: "Pay dividend" }).click();
  await expect(
    page.getByText("The dividend snapshot was paid once through the ledger."),
  ).toBeVisible();
  await expect(page.getByRole("cell", { name: "€1,600.00" })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});
