import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const profileId = "11111111-1111-4111-8111-111111111111";
const targetId = "22222222-2222-4222-8222-222222222222";
const specialistId = "33333333-3333-4333-8333-333333333333";
const reportId = "44444444-4444-4444-8444-444444444444";
const marketReportId = "55555555-5555-4555-8555-555555555555";
const offerId = "66666666-6666-4666-8666-666666666666";

const fulfill = async (route: Route, body: unknown, status = 200) => {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
};

async function mockIntelligenceApi(page: Page) {
  let reports: Array<Record<string, unknown>> = [];
  let operations: Array<Record<string, unknown>> = [];
  let actions: Array<Record<string, unknown>> = [];
  let offers: Array<Record<string, unknown>> = [
    {
      id: offerId,
      report_id: marketReportId,
      seller_profile_id: "77777777-7777-4777-8777-777777777777",
      buyer_profile_id: null,
      purchased_report_id: null,
      price_cents: 125_000,
      status: "open",
      expires_at: "2026-07-28T12:00:00Z",
      sold_at: null,
      created_at: "2026-07-27T12:00:00Z",
      category: "exchange",
      target_type: "profile",
      target_id: targetId,
      confidence_bps: 6_800,
    },
  ];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "intelligence-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "user-1",
        email: "analyst@example.invalid",
        display_name: "Chief Analyst",
        locale: "en",
      });
      return;
    }
    if (path === "/profiles/me") {
      await fulfill(route, {
        id: profileId,
        codename: "Chief Analyst",
        world_id: "world-1",
      });
      return;
    }
    if (path === "/pvp/targets") {
      await fulfill(route, [
        {
          profile_id: targetId,
          codename: "Rival Network",
          city_id: "city-1",
          cartel_id: null,
          cartel_name: null,
          public_reputation: { reliability: 50 },
          estimated_strength: "balanced",
          known_businesses: 1,
          known_district_presence: [],
          last_public_activity: "2026-07-27T11:00:00Z",
          treaty_status: null,
          protection_status: "open",
          recommendation: "balanced",
        },
      ]);
      return;
    }
    if (path === "/specialists") {
      await fulfill(route, [
        {
          id: specialistId,
          name: "Mara Voss",
          role: "market_analyst",
          level: 5,
          energy: 92,
          experience_points: 200,
          skills_json: { analysis: 82 },
          competence: 82,
          loyalty: 75,
          ambition: 50,
          stress: 8,
          exposure: 0,
          salary: 1500,
          salary_cents: 150_000,
          status: "hired",
          employer_company_id: null,
          assigned_operation_id: null,
          cooldown_until: null,
          hired_at: "2026-07-20T12:00:00Z",
        },
      ]);
      return;
    }
    if (path === "/intelligence/reports" && method === "GET") {
      await fulfill(route, reports);
      return;
    }
    if (path === "/intelligence/operations" && method === "GET") {
      await fulfill(route, operations);
      return;
    }
    if (path === "/intelligence/operations" && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as {
        target_profile_id: string;
        specialist_id: string;
        information_type: string;
        category: string;
      };
      const operation = {
        id: "operation-1",
        ...body,
        cost_cash_cents: 25_000,
        cost_intelligence: 15,
        success_chance_bps: 7_000,
        detection_chance_bps: 1_000,
        outcome: "partial",
        detected: false,
        investigation_pressure_delta: 1,
        report_id: reportId,
        cooldown_until: "2026-07-27T13:00:00Z",
        created_at: "2026-07-27T12:00:00Z",
      };
      operations = [operation];
      reports = [
        {
          id: reportId,
          owner_profile_id: profileId,
          target_type: "profile",
          target_id: targetId,
          information_type: body.information_type,
          category: body.category,
          statement:
            "Assessment for economy: the target's posture is only partially visible.",
          confidence_bps: 5_500,
          source_category: "market_analysis",
          source_report_id: null,
          tradable: true,
          observed_at: "2026-07-27T12:00:00Z",
          expires_at: "2026-07-28T00:00:00Z",
          created_at: "2026-07-27T12:00:00Z",
          is_expired: false,
          age_seconds: 0,
        },
      ];
      await fulfill(route, operation, 201);
      return;
    }
    if (
      path === `/intelligence/reports/${reportId}/sell` &&
      method === "POST"
    ) {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as { price_cents: number };
      offers = [
        ...offers,
        {
          id: "offer-owned",
          report_id: reportId,
          seller_profile_id: profileId,
          buyer_profile_id: null,
          purchased_report_id: null,
          price_cents: body.price_cents,
          status: "open",
          expires_at: "2026-07-28T00:00:00Z",
          sold_at: null,
          created_at: "2026-07-27T12:05:00Z",
          category: "economy",
          target_type: "profile",
          target_id: targetId,
          confidence_bps: 5_500,
        },
      ];
      await fulfill(route, offers.at(-1), 201);
      return;
    }
    if (path === "/intelligence/offers" && method === "GET") {
      await fulfill(route, offers);
      return;
    }
    if (path === `/intelligence/offers/${offerId}/buy` && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      offers = offers.map((offer) =>
        offer.id === offerId ? { ...offer, status: "sold" } : offer,
      );
      reports = [
        ...reports,
        {
          id: "purchased-copy",
          owner_profile_id: profileId,
          target_type: "profile",
          target_id: targetId,
          information_type: "analyzed",
          category: "exchange",
          statement: "A purchased exchange assessment.",
          confidence_bps: 6_800,
          source_category: "player_report_market",
          source_report_id: marketReportId,
          tradable: false,
          observed_at: "2026-07-27T11:00:00Z",
          expires_at: "2026-07-28T12:00:00Z",
          created_at: "2026-07-27T12:10:00Z",
          is_expired: false,
          age_seconds: 3600,
        },
      ];
      await fulfill(route, reports.at(-1));
      return;
    }
    if (path === "/strategic-actions/me") {
      await fulfill(route, actions);
      return;
    }
    if (path === "/strategic-actions/effects/me") {
      await fulfill(route, []);
      return;
    }
    if (path === "/strategic-actions" && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as Record<string, string>;
      const action = {
        id: "strategic-1",
        ...body,
        target_type: "profile",
        cost_cash_cents: 100_000,
        cost_intelligence: 40,
        success_chance_bps: 6_500,
        detection_chance_bps: 3_500,
        outcome: "success",
        detected: false,
        investigation_pressure_delta: 2,
        effect_id: "effect-1",
        cooldown_until: "2026-07-27T14:00:00Z",
        created_at: "2026-07-27T12:00:00Z",
      };
      actions = [action];
      await fulfill(route, action, 201);
      return;
    }
    if (path === "/resources") {
      await fulfill(route, {});
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

test("analyst gathers, trades and applies abstract pressure accessibly", async ({
  page,
}) => {
  await mockIntelligenceApi(page);
  await page.goto("/intelligence");
  await expect(
    page.getByRole("heading", {
      name: "Intelligence and strategic pressure",
    }),
  ).toBeVisible();

  const operationPanel = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "Information operation" }),
  });
  await operationPanel.getByLabel("Information type").selectOption("analyzed");
  await operationPanel
    .getByRole("button", { name: "Gather information" })
    .click();
  await expect(
    page.getByText("Information operation resolved and stored."),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Assessment for economy: the target's posture is only partially visible.",
    ),
  ).toBeVisible();

  const reportCard = page.locator(".subcard").filter({
    hasText:
      "Assessment for economy: the target's posture is only partially visible.",
  });
  await reportCard.getByLabel("Price in cents").fill("150000");
  await reportCard.getByRole("button", { name: "Offer report" }).click();
  await expect(page.getByText("Report offer created.")).toBeVisible();

  const market = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "Report market" }),
  });
  await market.getByRole("button", { name: "Buy copy" }).click();
  await expect(page.getByRole("dialog")).toContainText("€1,250.00");
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(
    page.getByText("An immutable report copy was purchased."),
  ).toBeVisible();

  const strategicPanel = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "Abstract strategic action" }),
  });
  await strategicPanel
    .getByLabel("Action type")
    .selectOption("make_information_unreliable");
  await strategicPanel
    .getByRole("button", { name: "Apply strategic pressure" })
    .click();
  await expect(
    page.getByText("Strategic action resolved and stored."),
  ).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
});
