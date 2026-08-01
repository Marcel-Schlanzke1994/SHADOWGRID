import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const ownCompanyId = "11111111-1111-4111-8111-111111111111";
const externalCompanyId = "22222222-2222-4222-8222-222222222222";
const externalIssueId = "33333333-3333-4333-8333-333333333333";
const ownIssueId = "44444444-4444-4444-8444-444444444444";

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
  id: ownCompanyId,
  world_id: "world-1",
  founder_profile_id: "profile-1",
  district_id: "district-1",
  industry: "technology",
  name: "Rhein Capital Systems",
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

const issue = (
  id: string,
  issuerCompanyId: string,
  issuerCompanyName: string,
  symbol: string,
  soldUnits: number,
  totalUnits: number,
) => ({
  id,
  world_id: "world-1",
  issuer_company_id: issuerCompanyId,
  issuer_company_name: issuerCompanyName,
  created_by_profile_id: "profile-2",
  symbol,
  title: `${symbol} growth bond`,
  face_value_cents: 100_000,
  total_units: totalUnits,
  sold_units: soldUnits,
  coupon_rate_bps: 800,
  term_periods: 3,
  coupons_paid: 0,
  status: "offering",
  default_reason: null,
  offering_ends_at: "2026-07-28T12:00:00Z",
  starts_at: null,
  ends_at: null,
  next_coupon_at: null,
  activated_at: null,
  repaid_at: null,
  defaulted_at: null,
  cancelled_at: null,
  created_at: "2026-07-27T12:00:00Z",
  holder_count: soldUnits > 0 ? 1 : 0,
});

async function mockBondApi(page: Page) {
  let issues = [
    issue(
      externalIssueId,
      externalCompanyId,
      "Domstadt Ventures",
      "DOM1",
      0,
      1,
    ),
    issue(ownIssueId, ownCompanyId, company.name, "RCS2", 1, 5),
  ];
  let holdings: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "bond-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "user-1",
        email: "bond@example.invalid",
        display_name: "Bond Operator",
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
    if (path === "/bonds/config") {
      await fulfill(route, {
        coupon_interval_minutes: 1_440,
        offering_minutes: 1_440,
        max_principal_cents: 100_000_000,
        max_term_periods: 30,
        default_reputation_penalty_bps: 1_000,
        default_investigation_penalty_bps: 1_250,
      });
      return;
    }
    if (path === "/bonds/issues" && method === "GET") {
      await fulfill(route, issues);
      return;
    }
    if (path === "/bonds/holdings/me") {
      await fulfill(route, holdings);
      return;
    }
    if (path === "/bonds/issues" && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as {
        symbol: string;
        title: string;
        total_units: number;
      };
      expect(body.symbol).toBe("NEW3");
      const created = {
        ...issue(
          "55555555-5555-4555-8555-555555555555",
          ownCompanyId,
          company.name,
          body.symbol,
          0,
          body.total_units,
        ),
        ...body,
      };
      issues = [created, ...issues];
      await fulfill(route, created, 201);
      return;
    }
    if (
      path === `/bonds/issues/${externalIssueId}/subscribe` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      expect(request.postDataJSON()).toEqual({ quantity: 1 });
      issues = issues.map((item) =>
        item.id === externalIssueId
          ? {
              ...item,
              sold_units: 1,
              status: "active",
              starts_at: "2026-07-27T12:10:00Z",
              ends_at: "2026-07-30T12:10:00Z",
              next_coupon_at: "2026-07-28T12:10:00Z",
              activated_at: "2026-07-27T12:10:00Z",
              holder_count: 1,
            }
          : item,
      );
      holdings = [
        {
          id: "holding-1",
          issue_id: externalIssueId,
          symbol: "DOM1",
          title: "DOM1 growth bond",
          issuer_company_name: "Domstadt Ventures",
          profile_id: "profile-1",
          quantity: 1,
          face_value_cents: 100_000,
          coupon_rate_bps: 800,
          issue_status: "active",
          acquired_at: "2026-07-27T12:10:00Z",
          updated_at: "2026-07-27T12:10:00Z",
        },
      ];
      await fulfill(
        route,
        {
          id: "subscription-1",
          issue_id: externalIssueId,
          subscriber_profile_id: "profile-1",
          quantity: 1,
          amount_cents: 100_000,
          transaction_id: "transaction-1",
          created_at: "2026-07-27T12:10:00Z",
        },
        201,
      );
      return;
    }
    if (path === `/bonds/issues/${ownIssueId}/activate` && method === "POST") {
      issues = issues.map((item) =>
        item.id === ownIssueId
          ? {
              ...item,
              status: "active",
              starts_at: "2026-07-27T12:15:00Z",
              ends_at: "2026-07-30T12:15:00Z",
              next_coupon_at: "2026-07-28T12:15:00Z",
              activated_at: "2026-07-27T12:15:00Z",
            }
          : item,
      );
      await fulfill(
        route,
        issues.find((item) => item.id === ownIssueId),
      );
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

test("player issues, subscribes to and activates company bonds", async ({
  page,
}) => {
  await mockBondApi(page);
  await page.goto("/bonds");

  await expect(
    page.getByRole("heading", { name: "Company bonds" }),
  ).toBeVisible();
  await page.getByLabel("Bond symbol").fill("NEW3");
  await page.getByLabel("Issue title").fill("New infrastructure bond");
  await page.getByRole("button", { name: "Publish issue" }).click();
  await expect(page.getByText("Bond issue published.")).toBeVisible();
  await expect(page.getByText(/NEW3 · New infrastructure bond/)).toBeVisible();

  await page.getByLabel("Bond issue").selectOption(externalIssueId);
  await page.getByRole("button", { name: "Review subscription" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Cash remains reserved by the issuer",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Subscribe" })
    .click();
  await expect(
    page.getByText("Bond subscription booked through the ledger."),
  ).toBeVisible();

  const ownIssue = page.locator("article").filter({
    has: page.getByText(/RCS2 · RCS2 growth bond/),
  });
  await ownIssue.getByRole("button", { name: "Activate issue" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Reserved proceeds become available.",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Activate issue" })
    .click();
  await expect(page.getByText("Bond issue activated.")).toBeVisible();

  const portfolio = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "Bond holdings" }),
  });
  await expect(portfolio.getByText(/DOM1 · 1 units/)).toBeVisible();
  await expect(portfolio.getByText("€1,000.00")).toBeVisible();
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});
