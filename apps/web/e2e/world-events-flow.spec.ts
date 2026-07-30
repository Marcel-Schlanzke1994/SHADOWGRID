import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const worldId = "11111111-1111-4111-8111-111111111111";
const definitionId = "22222222-2222-4222-8222-222222222222";
const instanceId = "33333333-3333-4333-8333-333333333333";

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

const baseProfile = {
  id: "profile-1",
  world_id: worldId,
  city_id: "city-1",
  codename: "Event Controller",
  archetype: "family_network",
  home_district_id: "district-1",
  tutorial_step: 7,
  loyalty: 72,
  legitimacy: 68,
  fear: 18,
  investigation_pressure: 24,
  stress: 14,
  stability: 79,
  operation_slots: 3,
  protected_until: "2026-08-01T00:00:00Z",
  recovery_until: null,
  resources: {
    cash: 12_000_000,
    capital: 4_500_000,
    influence: 32,
    intelligence: 21,
    logistics_capacity: 10,
    personnel_capacity: 12,
    version: 1,
  },
};

async function mockWorldEventApi(page: Page) {
  let instances: Array<Record<string, unknown>> = [];
  let previewRequests = 0;

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "world-event-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "admin-1",
        email: "admin@example.invalid",
        display_name: "Event Controller",
        locale: "en",
        email_verified: true,
        is_admin: true,
        is_moderator: true,
      });
      return;
    }
    if (path === "/profiles/me") {
      await fulfill(route, baseProfile);
      return;
    }
    if (path === "/admin/summary") {
      await fulfill(route, { users: 3, worlds: 1, active_events: 0 });
      return;
    }
    if (path === "/admin/world-events/definitions") {
      await fulfill(route, [
        {
          id: definitionId,
          event_key: "technology_boom",
          version: 1,
          title: "Technology boom",
          description: "Technology demand surges while specialist costs rise.",
          default_scope_type: "world",
          default_duration_minutes: 720,
          effect_config_json: {
            demand_multiplier_bps: 12_500,
            specialist_salary_multiplier_bps: 11_500,
          },
          enabled: true,
          created_at: "2026-07-27T08:00:00Z",
        },
      ]);
      return;
    }
    if (path === "/world-events/current") {
      await fulfill(route, instances);
      return;
    }
    if (path === "/admin/world-events/preview" && method === "POST") {
      previewRequests += 1;
      expect(instances).toEqual([]);
      const body = request.postDataJSON() as {
        world_id: string;
        event_key: string;
        starts_at: string;
        duration_minutes: number;
      };
      expect(body.world_id).toBe(worldId);
      expect(body.event_key).toBe("technology_boom");
      await fulfill(route, {
        definition_id: definitionId,
        event_key: body.event_key,
        template_version: 1,
        title: "Technology boom",
        description: "Technology demand surges while specialist costs rise.",
        scope_type: "world",
        scope_id: worldId,
        starts_at: body.starts_at,
        ends_at: "2026-07-28T00:00:00Z",
        effect_config: {
          demand_multiplier_bps: 12_500,
          specialist_salary_multiplier_bps: 11_500,
        },
        affected_companies: 4,
      });
      return;
    }
    if (path === "/admin/world-events/activate" && method === "POST") {
      expect(previewRequests).toBe(1);
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      const body = request.postDataJSON() as { starts_at: string };
      const instance = {
        id: instanceId,
        world_id: worldId,
        definition_id: definitionId,
        event_key: "technology_boom",
        template_version: 1,
        title: "Technology boom",
        description: "Technology demand surges while specialist costs rise.",
        status: "scheduled",
        scope_type: "world",
        scope_id: worldId,
        effect_config_json: {
          demand_multiplier_bps: 12_500,
          specialist_salary_multiplier_bps: 11_500,
        },
        starts_at: body.starts_at,
        ends_at: "2026-07-28T00:00:00Z",
        activated_at: null,
        ended_at: null,
        end_reason: null,
        created_at: "2026-07-27T12:00:00Z",
      };
      instances = [instance];
      await fulfill(route, instance, 201);
      return;
    }
    if (path === `/admin/world-events/${instanceId}/end` && method === "POST") {
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      instances = instances.map((instance) => ({
        ...instance,
        status: "ended",
        ended_at: "2026-07-27T12:05:00Z",
        end_reason: "Ended by local administrator.",
      }));
      await fulfill(route, instances[0]);
      return;
    }
    if (path === "/operations") {
      await fulfill(route, []);
      return;
    }
    if (path === "/world-events") {
      await fulfill(route, [
        {
          id: instanceId,
          world_id: worldId,
          definition_id: definitionId,
          event_key: "technology_boom",
          template_version: 1,
          title: "Technology boom",
          description: "Technology demand surges while specialist costs rise.",
          status: "active",
          scope_type: "world",
          scope_id: worldId,
          effect_config_json: { demand_multiplier_bps: 12_500 },
          starts_at: "2026-07-27T11:00:00Z",
          ends_at: "2026-07-28T00:00:00Z",
          activated_at: "2026-07-27T11:00:00Z",
          ended_at: null,
          end_reason: null,
          created_at: "2026-07-27T10:00:00Z",
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

test("administrator previews, activates and safely ends a world event", async ({
  page,
}) => {
  await mockWorldEventApi(page);
  await page.goto("/admin");
  await expect(
    page.getByRole("heading", { name: "World-event control" }),
  ).toBeVisible();

  const eventPanel = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "World-event control" }),
  });
  await eventPanel.getByRole("button", { name: "Preview event" }).click();

  const confirmation = page.getByRole("dialog");
  await expect(confirmation).toContainText("Technology boom");
  await expect(confirmation).toContainText("4 affected companies");
  await confirmation.getByRole("button", { name: "Activate event" }).click();
  await expect(page.getByText("World event activated.")).toBeVisible();
  await expect(
    eventPanel.getByText("Technology boom", { exact: true }),
  ).toBeVisible();

  await eventPanel.getByRole("button", { name: "End event" }).click();
  await expect(page.getByText("World event ended safely.")).toBeVisible();
  await expect(eventPanel.locator(".status")).toContainText("ended");
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});

test("active world event is visible in the player command center", async ({
  page,
}) => {
  await mockWorldEventApi(page);
  await page.goto("/command");

  const banner = page.getByRole("region", { name: "Active world event" });
  await expect(banner).toContainText("Technology boom");
  await expect(banner).toContainText(
    "Technology demand surges while specialist costs rise.",
  );
  await expect(
    page
      .locator(".panel")
      .filter({ has: page.getByRole("heading", { name: "Cologne news" }) }),
  ).toContainText("Technology boom");
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});
