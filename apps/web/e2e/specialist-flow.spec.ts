import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const company = {
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

const candidate = {
  id: "candidate-1",
  world_id: "world-1",
  city_id: "city-1",
  market_cycle_key: "2026-07-26",
  role: "market_analyst",
  name: "Leonie Adler",
  level: 2,
  salary_cents: 125_000,
  loyalty: 74,
  energy: 91,
  skills_json: {
    market_intelligence: 82,
    leadership: 61,
    resilience: 72,
  },
  status: "available",
  available_until: "2026-07-27T00:00:00Z",
};

const hiredSpecialist = {
  id: "specialist-1",
  name: candidate.name,
  role: candidate.role,
  level: candidate.level,
  energy: candidate.energy,
  experience_points: 10,
  skills_json: candidate.skills_json,
  competence: 82,
  loyalty: candidate.loyalty,
  ambition: 61,
  stress: 0,
  exposure: 0,
  salary: 1_250,
  salary_cents: candidate.salary_cents,
  status: "hired",
  employer_company_id: company.id,
  assigned_operation_id: null,
  cooldown_until: null,
  hired_at: "2026-07-26T12:30:00Z",
};

async function mockSpecialistApi(page: Page) {
  let specialists: (typeof hiredSpecialist)[] = [];
  let market = [candidate];

  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ access_token: "e2e-specialist-token" }),
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
  await page.route("**/api/v1/companies", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([company]),
    }),
  );
  await page.route("**/api/v1/specialist-market", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(market),
    }),
  );
  await page.route("**/api/v1/specialists", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(specialists),
    }),
  );
  await page.route(
    "**/api/v1/specialist-market/candidate-1/hire",
    async (route) => {
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      expect(route.request().postDataJSON()).toEqual({
        company_id: company.id,
      });
      specialists = [{ ...hiredSpecialist }];
      market = [];
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(hiredSpecialist),
      });
    },
  );
  await page.route(
    "**/api/v1/companies/company-1/specialist-effects",
    (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          active_specialists: 1,
          capacity_bonus_units: 0,
          revenue_bonus_bps: 610,
          cost_reduction_bps: 0,
          attractiveness_bonus_points: 0,
        }),
      }),
  );
  await page.route(
    "**/api/v1/specialists/specialist-1/payroll-reports",
    (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "payroll-report-1",
            payroll_tick_id: "payroll-tick-1",
            specialist_id: hiredSpecialist.id,
            company_id: company.id,
            transaction_id: "transaction-1",
            salary_due_cents: candidate.salary_cents,
            salary_paid_cents: candidate.salary_cents,
            unpaid_cents: 0,
            loyalty_before: 73,
            loyalty_after: 74,
            energy_before: 83,
            energy_after: 91,
            level_before: 2,
            level_after: 2,
            created_at: "2026-07-26T13:00:00Z",
          },
        ]),
      }),
  );
  await page.route(
    "**/api/v1/specialists/specialist-1/assign",
    async (route) => {
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      expect(route.request().postDataJSON()).toEqual({
        company_id: company.id,
      });
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(hiredSpecialist),
      });
    },
  );
  await page.route(
    "**/api/v1/specialists/specialist-1/release",
    async (route) => {
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      specialists = [];
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          ...hiredSpecialist,
          status: "released",
          employer_company_id: null,
        }),
      });
    },
  );
}

test("specialist hiring, assignment and release are explicit and accessible", async ({
  page,
}) => {
  await mockSpecialistApi(page);
  await page.goto("/specialists");

  await expect(
    page.getByRole("heading", { level: 1, name: "Specialists" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 3, name: candidate.name }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Hire" }).click();
  const hireDialog = page.getByRole("dialog");
  await expect(hireDialog).toContainText("€1,250.00");
  await hireDialog.getByRole("button", { name: "Hire" }).click();

  await expect(
    page.getByText("The specialist was hired successfully."),
  ).toBeVisible();
  await page.getByRole("link", { name: /Leonie Adler/ }).click();
  await expect(
    page.getByRole("heading", {
      level: 3,
      name: "Transparent company effects",
    }),
  ).toBeVisible();
  await expect(page.getByText("+6.1%")).toBeVisible();
  await expect(page.getByLabel("Payroll history")).toContainText("€1,250.00");

  await page.getByRole("button", { name: "Assign" }).click();
  await expect(
    page.getByText("The specialist was assigned successfully."),
  ).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);

  await page.getByRole("button", { name: "Release" }).click();
  const releaseDialog = page.getByRole("dialog");
  await expect(releaseDialog).toContainText(
    "Active company effects will end immediately.",
  );
  await releaseDialog.getByRole("button", { name: "Release" }).click();
  await expect(
    page.getByText("The specialist was released successfully."),
  ).toBeVisible();
});
