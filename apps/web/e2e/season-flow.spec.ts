import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const worldId = "11111111-1111-4111-8111-111111111111";
const seasonId = "22222222-2222-4222-8222-222222222222";
const templateId = "33333333-3333-4333-8333-333333333333";

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

const schedule = [
  { phase: "setup", ends_at: "2026-07-27T12:30:00Z" },
  { phase: "early", ends_at: "2026-07-28T12:00:00Z" },
  { phase: "mid", ends_at: "2026-07-30T12:00:00Z" },
  { phase: "late", ends_at: "2026-08-01T12:00:00Z" },
  { phase: "scoring", ends_at: "2026-08-02T12:00:00Z" },
];

const baseSeason = {
  id: seasonId,
  world_id: worldId,
  template_id: templateId,
  season_number: 0,
  name: "Cologne founding season 0",
  phase: "setup",
  status: "active",
  goals_json: [
    { key: "build_company", title: "Build a sustainable company", target: 1 },
    { key: "form_cartel", title: "Coordinate a cartel", target: 1 },
  ],
  scoring_categories_json: [
    "wealthiest_player",
    "portfolio_value",
    "entrepreneur",
    "largest_company",
    "strongest_cartel",
    "largest_public_company",
    "dividend_yield",
    "district_control",
    "diplomacy",
    "information_network",
    "stability",
    "crisis_recovery",
  ],
  phase_schedule_json: schedule,
  starting_cash_cents: 8_000_000,
  starts_at: "2026-07-27T12:00:00Z",
  ends_at: "2026-08-02T12:00:00Z",
  phase_changed_at: "2026-07-27T12:00:00Z",
  scoring_started_at: null,
  closed_at: null,
  archived_at: null,
  created_at: "2026-07-27T12:00:00Z",
  phase_ends_at: "2026-07-27T12:30:00Z",
  remaining_seconds: 1_800,
};

async function mockSeasonApi(page: Page) {
  let currentSeason: Record<string, unknown> = { ...baseSeason };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "season-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "admin-1",
        email: "season-admin@example.invalid",
        display_name: "Season Administrator",
        locale: "en",
        email_verified: true,
        is_admin: true,
        is_moderator: true,
      });
      return;
    }
    if (path === "/profiles/me") {
      await fulfill(route, {
        id: "profile-1",
        world_id: worldId,
        city_id: "city-1",
        codename: "Season Administrator",
        resources: {
          cash: 80_000,
          capital: 20_000,
          influence: 25,
          intelligence: 10,
        },
      });
      return;
    }
    if (path === "/seasons/current") {
      await fulfill(route, currentSeason);
      return;
    }
    if (path.startsWith(`/seasons/${seasonId}/leaderboards/`)) {
      const category = path.split("/").at(-1);
      await fulfill(
        route,
        category === "largest_company"
          ? [
              {
                category,
                entity_type: "company",
                entity_id: "company-1",
                entity_name: "Rhein Systems AG",
                score_value: 25_000_000,
                rank: 1,
                tied: false,
                metrics_json: { enterprise_value_cents: 25_000_000 },
                captured_at: null,
              },
            ]
          : [
              {
                category,
                entity_type: "profile",
                entity_id: "profile-1",
                entity_name: "Season Administrator",
                score_value: 8_000_000,
                rank: 1,
                tied: true,
                metrics_json: { cash_cents: 8_000_000 },
                captured_at: null,
              },
              {
                category,
                entity_type: "profile",
                entity_id: "profile-2",
                entity_name: "Equal Rival",
                score_value: 8_000_000,
                rank: 1,
                tied: true,
                metrics_json: { cash_cents: 8_000_000 },
                captured_at: null,
              },
            ],
      );
      return;
    }
    if (path === "/hall-of-fame") {
      await fulfill(route, [
        {
          id: "hall-1",
          season_id: "old-season",
          season_number: 0,
          category: url.searchParams.get("category"),
          entity_type: "profile",
          entity_id: "profile-1",
          entity_name: "Season Administrator",
          score_value: 7_500_000,
          rank: 1,
          tied: false,
          metrics_json: {},
          awarded_at: "2026-07-20T12:00:00Z",
        },
      ]);
      return;
    }
    if (path === "/account/rewards/me") {
      await fulfill(route, [
        {
          id: "reward-1",
          season_id: "old-season",
          reward_type: "title",
          reward_key: "season:0:wealthiest_player:champion",
          label: "Wealthiest Player Champion",
          metadata_json: { rank: 1 },
          awarded_at: "2026-07-20T12:00:00Z",
        },
      ]);
      return;
    }
    if (path === "/admin/summary") {
      await fulfill(route, { users: 3, worlds: 1, seasons: 1 });
      return;
    }
    if (path === "/admin/seasons" && method === "GET") {
      await fulfill(route, [currentSeason]);
      return;
    }
    if (path === "/admin/seasons/templates") {
      await fulfill(route, [
        {
          id: templateId,
          template_key: "cologne_standard",
          version: 1,
          name: "Cologne founding season",
          duration_minutes: 20_160,
          phase_weights_json: {
            setup: 500,
            early: 2_500,
            mid: 3_500,
            late: 2_500,
            scoring: 1_000,
          },
          goals_json: baseSeason.goals_json,
          scoring_categories_json: baseSeason.scoring_categories_json,
          starting_cash_cents: 8_000_000,
          enabled: true,
          created_at: "2026-07-27T12:00:00Z",
        },
      ]);
      return;
    }
    if (path === `/admin/seasons/${seasonId}/shorten` && method === "POST") {
      const body = request.postDataJSON() as { duration_minutes: number };
      expect(body.duration_minutes).toBe(60);
      currentSeason = {
        ...currentSeason,
        ends_at: "2026-07-27T13:00:00Z",
      };
      await fulfill(route, currentSeason);
      return;
    }
    if (path === `/admin/seasons/${seasonId}/simulate` && method === "POST") {
      currentSeason = {
        ...currentSeason,
        phase: "mid",
        phase_ends_at: "2026-07-27T12:45:00Z",
      };
      await fulfill(route, currentSeason);
      return;
    }
    if (path === `/admin/seasons/${seasonId}/close` && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      currentSeason = {
        ...currentSeason,
        phase: "archived",
        status: "archived",
        remaining_seconds: 0,
        closed_at: "2026-07-27T12:30:00Z",
        archived_at: "2026-07-27T12:30:00Z",
      };
      await fulfill(route, {
        season: currentSeason,
        score_count: 20,
        hall_of_fame_count: 12,
        reward_count: 3,
        archive_count: 8,
      });
      return;
    }
    if (path === "/admin/seasons" && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      currentSeason = {
        ...baseSeason,
        id: "new-season",
        season_number: 1,
        name: "Cologne founding season 1",
      };
      await fulfill(route, currentSeason, 201);
      return;
    }
    if (path === "/admin/world-events/definitions") {
      await fulfill(route, []);
      return;
    }
    if (path === "/world-events/current") {
      await fulfill(route, []);
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

test("player sees season phase, goals, ties, rewards and champions", async ({
  page,
}) => {
  await mockSeasonApi(page);
  await page.goto("/rankings");

  await expect(
    page.getByRole("heading", { name: "Season rankings" }),
  ).toBeVisible();
  await expect(page.getByText("Cologne founding season 0")).toBeVisible();
  await expect(page.getByText("Build a sustainable company")).toBeVisible();
  await expect(page.getByText("Equal Rival")).toBeVisible();
  await expect(page.getByText("Tied").first()).toBeVisible();
  await expect(page.getByText("Wealthiest Player Champion")).toBeVisible();

  await page.getByLabel("Ranking category").selectOption("largest_company");
  await expect(page.getByText("Rhein Systems AG")).toBeVisible();
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});

test("local administrator shortens, simulates, closes and recreates a season", async ({
  page,
}) => {
  await mockSeasonApi(page);
  await page.goto("/admin");

  const panel = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "Season control" }),
  });
  await panel.getByLabel("Total duration in minutes").fill("60");
  await panel.getByRole("button", { name: "Shorten season" }).click();
  await expect(page.getByText("Season schedule shortened.")).toBeVisible();

  await panel.getByLabel("Simulate state at").fill("2026-07-27T12:40");
  await panel.getByRole("button", { name: "Simulate season" }).click();
  await expect(page.getByText("Season phase simulated.")).toBeVisible();
  await expect(panel.locator(".status")).toContainText(/mid/i);

  await panel.getByRole("button", { name: "Close and archive season" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Financial history remains immutable.",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close and archive season" })
    .click();
  await expect(
    page.getByText(/Season archived with 20 score snapshots/),
  ).toBeVisible();

  await panel
    .getByRole("button", { name: "Create next season from template" })
    .click();
  await expect(
    page.getByText("New season created from the versioned template."),
  ).toBeVisible();
  await expect(panel.getByText("Season 1")).toBeVisible();
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});
