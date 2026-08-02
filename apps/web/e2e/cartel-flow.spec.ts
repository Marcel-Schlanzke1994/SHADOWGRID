import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const cartelId = "11111111-1111-4111-8111-111111111111";
const districtId = "22222222-2222-4222-8222-222222222222";
const cityId = "33333333-3333-4333-8333-333333333333";

const fulfill = async (route: Route, body: unknown, status = 200) => {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
};

async function mockCartelApi(page: Page) {
  let treasury = {
    cartel_id: cartelId,
    balance_cents: 2_000_000,
    reserved_cents: 0,
    approval_threshold_cents: 250_000,
    single_spend_limit_cents: 2_500_000,
  };
  let expenses: Array<Record<string, unknown>> = [];
  let projects: Array<Record<string, unknown>> = [];
  const cartel = {
    id: cartelId,
    world_id: "world-1",
    city_id: cityId,
    name: "Rheinbund",
    tag: "RHB",
    archetype: "business_consortium",
    description: "A coordinated logistics cartel.",
    governance_model: "directorate",
    stability: 78,
    reputation: 65,
    investigation_pressure: 10,
    approval_threshold_cents: 250_000,
    single_spend_limit_cents: 2_500_000,
    status: "active",
    member_limit: 20,
    member_count: 2,
    treasury_balance_cents: 2_000_000,
    my_role: "leader",
    my_permissions: ["*"],
  };

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "cartel-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "user-1",
        email: "leader@example.invalid",
        display_name: "Cartel Leader",
        locale: "en",
      });
      return;
    }
    if (path === "/profiles/me") {
      await fulfill(route, {
        id: "profile-1",
        user_id: "user-1",
        world_id: "world-1",
        city_id: cityId,
        home_district_id: districtId,
        codename: "Cartel Leader",
        archetype: "business_consortium",
      });
      return;
    }
    if (path === "/cartels" && method === "GET") {
      await fulfill(route, [cartel]);
      return;
    }
    if (path === `/cartels/${cartelId}` && method === "GET") {
      await fulfill(route, cartel);
      return;
    }
    if (path === "/cartels/invitations/me") {
      await fulfill(route, []);
      return;
    }
    if (path === "/leaderboards/cartels/current") {
      await fulfill(route, [
        {
          rank: 1,
          cartel_id: cartelId,
          name: "Rheinbund",
          tag: "RHB",
          season_number: 1,
          score: 920,
          treasury_cents: treasury.balance_cents,
          member_count: 2,
          completed_projects: 0,
          influence: 80,
        },
      ]);
      return;
    }
    if (path === "/districts") {
      await fulfill(route, [
        {
          id: districtId,
          slug: "harbor",
          name: "Iron Harbor",
          prosperity: 60,
          employment: 60,
          safety: 50,
          authority_presence: 40,
          digital_infrastructure: 55,
          property_value: 50,
          public_trust: 50,
          media_attention: 40,
          economic_activity: 70,
          social_stability: 55,
          map_x: 10,
          map_y: 10,
          map_points: "",
          influence: {},
        },
      ]);
      return;
    }
    if (path === `/cartels/${cartelId}/members`) {
      await fulfill(route, [
        {
          profile_id: "profile-1",
          codename: "Cartel Leader",
          role: "leader",
          status: "active",
          joined_at: "2026-07-27T09:00:00Z",
        },
        {
          profile_id: "profile-2",
          codename: "Finance Lead",
          role: "finance_lead",
          status: "active",
          joined_at: "2026-07-27T10:00:00Z",
        },
      ]);
      return;
    }
    if (path === `/cartels/${cartelId}/treasury` && method === "GET") {
      await fulfill(route, treasury);
      return;
    }
    if (path === `/cartels/${cartelId}/treasury/deposit` && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as { amount_cents: number };
      treasury = {
        ...treasury,
        balance_cents: treasury.balance_cents + body.amount_cents,
      };
      await fulfill(route, treasury);
      return;
    }
    if (path === `/cartels/${cartelId}/treasury/expenses` && method === "GET") {
      await fulfill(route, expenses);
      return;
    }
    if (
      path === `/cartels/${cartelId}/treasury/expenses` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as {
        amount_cents: number;
        purpose: string;
      };
      expenses = [
        {
          id: "expense-1",
          organization_id: cartelId,
          requested_by_profile_id: "profile-1",
          approved_by_profile_id: null,
          amount_cents: body.amount_cents,
          purpose: body.purpose,
          requires_approval: true,
          status: "pending",
          transaction_id: null,
          requested_at: "2026-07-27T11:00:00Z",
          resolved_at: null,
        },
      ];
      await fulfill(route, expenses[0], 201);
      return;
    }
    if (
      path === `/cartels/${cartelId}/treasury/expenses/expense-1/approve` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      expenses = expenses.map((item) => ({
        ...item,
        approved_by_profile_id: "profile-2",
        status: "approved",
        transaction_id: "transaction-1",
        resolved_at: "2026-07-27T11:10:00Z",
      }));
      treasury = {
        ...treasury,
        balance_cents: treasury.balance_cents - 300_000,
      };
      await fulfill(route, expenses[0]);
      return;
    }
    if (path === `/cartels/${cartelId}/projects` && method === "GET") {
      await fulfill(route, projects);
      return;
    }
    if (path === `/cartels/${cartelId}/projects` && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as {
        project_type: string;
        district_id: string;
      };
      projects = [
        {
          id: "project-1",
          organization_id: cartelId,
          district_id: body.district_id,
          project_type: body.project_type,
          title: "Media campaign",
          status: "active",
          required_cash_cents: 750_000,
          required_influence: 60,
          required_intelligence: 20,
          contributed_cash_cents: 0,
          contributed_influence: 0,
          contributed_intelligence: 0,
          influence_kind: "social",
          influence_reward: 55,
          starts_at: "2026-07-27T11:00:00Z",
          ends_at: "2026-07-29T11:00:00Z",
          completed_at: null,
          progress_bps: 0,
        },
      ];
      await fulfill(route, projects[0], 201);
      return;
    }
    if (
      path === `/cartels/${cartelId}/projects/project-1/contribute` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as {
        resource_type: string;
        amount_units: number;
      };
      projects = projects.map((item) => ({
        ...item,
        contributed_cash_cents:
          body.resource_type === "cash" ? body.amount_units : 0,
        progress_bps: 3_333,
      }));
      await fulfill(route, projects[0]);
      return;
    }
    if (path === `/cartels/${cartelId}/activity`) {
      await fulfill(route, [
        {
          id: "activity-1",
          action: "cartel.created",
          metadata_json: {},
          created_at: "2026-07-27T09:00:00Z",
        },
      ]);
      return;
    }
    if (path === `/engagement/social/cartels/${cartelId}/delegations`) {
      await fulfill(route, []);
      return;
    }
    if (path === `/engagement/social/cartels/${cartelId}/pause`) {
      await fulfill(route, null);
      return;
    }
    if (path === `/engagement/social/cartels/${cartelId}/chronicle`) {
      await fulfill(route, []);
      return;
    }
    if (path === `/influence/cities/${cityId}`) {
      await fulfill(route, [
        {
          district_id: districtId,
          district_name: "Iron Harbor",
          status: "contested",
          controlling_cartel_id: null,
          controlling_cartel_name: null,
          top_points: 80,
          entries: [
            {
              cartel_id: cartelId,
              cartel_name: "Rheinbund",
              kind: "economic",
              points: 80,
            },
          ],
        },
      ]);
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

test("cartel leader manages treasury, projects and approvals accessibly", async ({
  page,
}) => {
  await mockCartelApi(page);
  await page.goto(`/cartels/${cartelId}`);
  await expect(page.getByRole("heading", { name: "Cartels" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "RHB · Rheinbund" }),
  ).toBeVisible();

  const treasuryPanel = page
    .locator(".panel")
    .filter({ has: page.getByRole("heading", { name: "Treasury" }) });
  await treasuryPanel.getByLabel("Amount in cents").first().fill("100000");
  await treasuryPanel
    .getByRole("button", { name: "Deposit into treasury" })
    .click();
  await expect(page.getByText("Treasury deposit posted.")).toBeVisible();

  const projectsPanel = page
    .locator(".panel")
    .filter({ has: page.getByRole("heading", { name: "Cartel projects" }) });
  await projectsPanel.getByLabel("Project type").selectOption("media_campaign");
  await projectsPanel.getByRole("button", { name: "Start project" }).click();
  await expect(page.getByText("Cartel project started.")).toBeVisible();
  await projectsPanel.getByLabel("Contribution amount").fill("750000");
  await projectsPanel.getByRole("button", { name: "Contribute" }).click();
  await expect(page.getByText("Project contribution posted.")).toBeVisible();

  await treasuryPanel.getByLabel("Expense purpose").fill("District campaign");
  await treasuryPanel.getByLabel("Amount in cents").last().fill("300000");
  await treasuryPanel.getByRole("button", { name: "Request expense" }).click();
  await expect(page.getByText("Expense request recorded.")).toBeVisible();
  await treasuryPanel.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("dialog")).toContainText("€3,000.00");
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Cartel action completed.")).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
});
