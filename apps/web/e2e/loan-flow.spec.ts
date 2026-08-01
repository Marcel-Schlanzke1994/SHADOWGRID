import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const companyId = "11111111-1111-4111-8111-111111111111";
const applicationId = "22222222-2222-4222-8222-222222222222";

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
  name: "Rhein Finance Systems",
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

async function mockLoanApi(page: Page) {
  let applications: Array<Record<string, unknown>> = [];
  let loans: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "loan-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "user-1",
        email: "loan@example.invalid",
        display_name: "Finance Operator",
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
    if (path === "/loans/config") {
      await fulfill(route, {
        payment_interval_minutes: 1_440,
        offer_valid_minutes: 1_440,
        max_principal_cents: 100_000_000,
        max_term_periods: 30,
        min_interest_rate_bps: 200,
        max_interest_rate_bps: 5_000,
        default_reputation_penalty_bps: 750,
        default_investigation_penalty_bps: 1_000,
      });
      return;
    }
    if (path === "/loans/applications/me") {
      await fulfill(route, applications);
      return;
    }
    if (path === "/loans/me") {
      await fulfill(route, loans);
      return;
    }
    if (path === "/loans/applications" && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as {
        requested_principal_cents: number;
        term_periods: number;
        collateral_score_bps: number;
        purpose: string;
      };
      expect(body.purpose).toBe("Expand fictional cloud capacity");
      const application = {
        id: applicationId,
        world_id: "world-1",
        company_id: companyId,
        company_name: company.name,
        applicant_profile_id: "profile-1",
        ...body,
        offered_interest_rate_bps: 800,
        offered_installment_cents: 180_000,
        offered_total_repayment_cents: 540_000,
        status: "offered",
        rejection_reason: null,
        risk_snapshot_json: { lending_limit_cents: 10_000_000 },
        offer_expires_at: "2026-07-28T12:00:00Z",
        accepted_at: null,
        cancelled_at: null,
        created_at: "2026-07-27T12:00:00Z",
      };
      applications = [application];
      await fulfill(route, application, 201);
      return;
    }
    if (
      path === `/loans/applications/${applicationId}/accept` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      applications = applications.map((application) => ({
        ...application,
        status: "accepted",
        accepted_at: "2026-07-27T12:05:00Z",
      }));
      const loan = {
        id: "33333333-3333-4333-8333-333333333333",
        world_id: "world-1",
        application_id: applicationId,
        company_id: companyId,
        company_name: company.name,
        borrower_profile_id: "profile-1",
        principal_cents: 500_000,
        interest_rate_bps: 800,
        total_interest_cents: 40_000,
        total_repayment_cents: 540_000,
        scheduled_installment_cents: 180_000,
        term_periods: 3,
        payments_made: 0,
        outstanding_principal_cents: 500_000,
        outstanding_interest_cents: 40_000,
        collateral_score_bps: 5_000,
        status: "active",
        default_reason: null,
        disbursement_transaction_id: "44444444-4444-4444-8444-444444444444",
        starts_at: "2026-07-27T12:05:00Z",
        ends_at: "2026-07-30T12:05:00Z",
        next_payment_at: "2026-07-28T12:05:00Z",
        repaid_at: null,
        defaulted_at: null,
        cancelled_at: null,
        created_at: "2026-07-27T12:05:00Z",
      };
      loans = [loan];
      await fulfill(route, loan, 201);
      return;
    }
    await fulfill(
      route,
      {
        error: { code: "e2e.unhandled", message: `${method} ${path}` },
        server_time: "2026-07-27T12:00:00Z",
      },
      404,
    );
  });
}

test("player requests, reviews and accepts a fixed-rate company loan", async ({
  page,
}) => {
  await mockLoanApi(page);
  await page.goto("/finance");

  await expect(
    page.getByRole("heading", { name: "Company finance" }),
  ).toBeVisible();
  await page
    .getByLabel("Business purpose")
    .fill("Expand fictional cloud capacity");
  await page.getByRole("button", { name: "Request offer" }).click();
  await expect(
    page.getByText("A fixed-rate loan offer is available."),
  ).toBeVisible();
  await expect(page.getByText(/8% fixed rate/)).toBeVisible();

  await page.getByRole("button", { name: "Accept offer" }).click();
  await expect(page.getByRole("dialog")).toContainText("through the ledger");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Accept offer" })
    .click();

  await expect(
    page.getByText("Loan disbursed through the balanced company ledger."),
  ).toBeVisible();
  const portfolio = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "Company loans" }),
  });
  await expect(portfolio.getByText("Rhein Finance Systems")).toBeVisible();
  await expect(portfolio.getByText("0 of 3 installments paid")).toBeVisible();
  await expect(
    portfolio.getByText("Outstanding repayment: €5,400.00"),
  ).toBeVisible();
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});
