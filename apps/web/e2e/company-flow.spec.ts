import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const baseCompany = {
  id: "company-1",
  world_id: "world-1",
  founder_profile_id: "profile-1",
  district_id: "district-1",
  industry: "logistics",
  name: "RheinCargo Solutions",
  status: "private",
  account_balance_cents: 2_000_000,
  enterprise_value_cents: 20_000_000,
  revenue_cents: 3_500_000,
  cost_cents: 2_700_000,
  profit_cents: 800_000,
  debt_cents: 0,
  employees: 8,
  capacity: 3_000,
  quality: 5_000,
  market_share_bps: 120,
  reputation_bps: 4_800,
  compliance_bps: 6_000,
  innovation_bps: 4_200,
  risk_bps: 1_800,
  investigation_pressure_bps: 0,
  is_local_simulation: false,
  version: 1,
  created_at: "2026-07-26T12:00:00Z",
  updated_at: "2026-07-26T12:00:00Z",
};

const companyConfig = {
  founding_cost_cents: 2_000_000,
  industries: {
    gastronomy: { enterprise_value_cents: 20_000_000 },
    logistics: { enterprise_value_cents: 20_000_000 },
    technology: { enterprise_value_cents: 20_000_000 },
  },
  investments: {
    capacity: {
      cost_cents: 500_000,
      metric: "capacity",
      increase: 500,
    },
    quality: {
      cost_cents: 750_000,
      metric: "quality",
      increase: 400,
    },
    innovation: {
      cost_cents: 1_000_000,
      metric: "innovation_bps",
      increase: 600,
    },
    compliance: {
      cost_cents: 800_000,
      metric: "compliance_bps",
      increase: 500,
    },
  },
};

const companyEconomyReport = {
  id: "company-report-1",
  tick_id: "tick-1",
  market_report_id: "market-report-1",
  company_id: "company-1",
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

const mockCompanyApi = async (page: Page) => {
  let company: typeof baseCompany | null = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ access_token: "e2e-company-token" }),
    }),
  );
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "e2e-user",
        email: "player@example.invalid",
        display_name: "E2E Player",
        locale: "en",
      }),
    }),
  );
  await page.route("**/api/v1/districts", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "district-1",
          name: "Innenstadt",
          slug: "innenstadt",
          prosperity: 85,
          employment: 82,
          safety: 74,
          authority_presence: 86,
          digital_infrastructure: 92,
          property_value: 88,
          public_trust: 70,
          media_attention: 66,
          economic_activity: 91,
          social_stability: 78,
          map_x: 70,
          map_y: 8,
          map_points: "0,0 1,1",
          influence: {},
        },
      ]),
    }),
  );
  await page.route("**/api/v1/profiles/me", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "profile-1",
        world_id: "world-1",
        city_id: "city-1",
      }),
    }),
  );
  await page.route("**/api/v1/economy/status", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        last_tick: {
          id: "tick-1",
          world_id: "world-1",
          period_key: "2026-07-26T12:00:00Z",
          period_start: "2026-07-26T12:00:00Z",
          period_end: "2026-07-26T13:00:00Z",
          status: "completed",
          company_count: 1,
          market_count: 3,
          started_at: "2026-07-26T13:00:00Z",
          completed_at: "2026-07-26T13:00:01Z",
        },
        next_scheduled_at: "2026-07-26T14:00:00Z",
      }),
    }),
  );
  await page.route("**/api/v1/economy/competitors", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          ...baseCompany,
          id: "ai-company-1",
          name: "Domlinie Logistik",
          founder_profile_id: "ai-profile-1",
          market_share_bps: 2_400,
          is_local_simulation: true,
        },
      ]),
    }),
  );
  await page.route("**/api/v1/companies**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    if (url.pathname.endsWith("/companies/config")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(companyConfig),
      });
      return;
    }
    if (url.pathname.endsWith("/companies") && method === "GET") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(company ? [company] : []),
      });
      return;
    }
    if (url.pathname.endsWith("/companies") && method === "POST") {
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      expect(route.request().postDataJSON()).toEqual({
        name: "RheinCargo Solutions",
        industry: "logistics",
        district_id: "district-1",
      });
      company = { ...baseCompany };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(company),
      });
      return;
    }
    if (url.pathname.endsWith("/investments") && method === "POST") {
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      expect(route.request().postDataJSON()).toEqual({
        investment_type: "capacity",
      });
      company = {
        ...baseCompany,
        account_balance_cents: 2_500_000,
        capacity: 3_500,
        version: 2,
      };
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(company),
      });
      return;
    }
    if (url.pathname.endsWith("/economy-reports") && method === "GET") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([companyEconomyReport]),
      });
      return;
    }
    if (url.pathname.endsWith("/companies/company-1") && method === "GET") {
      const current = company ?? baseCompany;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          ...current,
          ownership: [
            {
              id: "ownership-1",
              company_id: current.id,
              owner_profile_id: current.founder_profile_id,
              ownership_bps: 10_000,
              created_at: current.created_at,
            },
          ],
          investments:
            current.version === 2
              ? [
                  {
                    id: "investment-1",
                    company_id: current.id,
                    investor_profile_id: current.founder_profile_id,
                    investment_type: "capacity",
                    amount_cents: 500_000,
                    metric_before: 3_000,
                    metric_after: 3_500,
                    created_at: current.updated_at,
                  },
                ]
              : [],
          metrics_history: [],
        }),
      });
      return;
    }
    await route.abort();
  });
  await page.route("**/api/v1/companies/config", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(companyConfig),
    }),
  );
  await page.route("**/api/v1/companies/company-1/economy-reports", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([companyEconomyReport]),
    }),
  );
  await page.route(
    "**/api/v1/companies/company-1/investments",
    async (route) => {
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      expect(route.request().postDataJSON()).toEqual({
        investment_type: "capacity",
      });
      company = {
        ...baseCompany,
        account_balance_cents: 2_500_000,
        capacity: 3_500,
        version: 2,
      };
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(company),
      });
    },
  );
  await page.route("**/api/v1/companies/company-1", async (route) => {
    const current = company ?? baseCompany;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...current,
        ownership: [
          {
            id: "ownership-1",
            company_id: current.id,
            owner_profile_id: current.founder_profile_id,
            ownership_bps: 10_000,
            created_at: current.created_at,
          },
        ],
        investments: [],
        metrics_history: [],
      }),
    });
  });
};

test("company founding and investment require cost confirmation", async ({
  page,
}) => {
  await mockCompanyApi(page);
  await page.goto("/companies");

  await expect(
    page.getByText("No company has been founded yet."),
  ).toBeVisible();
  await page.getByLabel("Business name").fill("RheinCargo Solutions");
  await page.getByLabel("Business type").selectOption("logistics");
  await page.getByLabel("Starting district").selectOption("district-1");
  await page.getByRole("button", { name: "Found company" }).click();

  const foundingDialog = page.getByRole("dialog");
  await expect(foundingDialog).toContainText("€20,000.00");
  await expect(
    foundingDialog.getByRole("button", { name: "Cancel" }),
  ).toBeFocused();
  await foundingDialog.getByRole("button", { name: "Found company" }).click();
  await expect(page).toHaveURL(/\/companies\/company-1$/);
  await expect(
    page.getByText("The company was founded successfully."),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 2, name: "RheinCargo Solutions" }),
  ).toBeVisible();
  await expect(
    page.getByText("Revenue, operating cost and profit over time"),
  ).toBeVisible();
  await expect(page.getByText("Next scheduled tick")).toBeVisible();

  await page.getByRole("button", { name: /Capacity/ }).click();
  const investmentDialog = page.getByRole("dialog");
  await expect(investmentDialog).toContainText("€5,000.00");
  await expect(
    investmentDialog.getByRole("button", { name: "Cancel" }),
  ).toBeFocused();
  await investmentDialog.getByRole("button", { name: "Invest" }).click();
  await expect(
    page.getByText("The investment was booked successfully."),
  ).toBeVisible();
  await expect(page.getByText("€25,000.00").first()).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});
