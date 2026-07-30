import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

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

async function mockRealtimeUxApi(page: Page) {
  let notifications = [
    {
      id: "11111111-1111-4111-8111-111111111111",
      event_type: "company.warning.created",
      title: "Liquidity warning",
      body: "A company payment requires review.",
      metadata_json: { company_id: "company-1" },
      read_at: null as string | null,
      created_at: "2026-07-28T08:00:00Z",
    },
    {
      id: "22222222-2222-4222-8222-222222222222",
      event_type: "cartel.invitation.created",
      title: "Cartel invitation",
      body: "An invitation is waiting.",
      metadata_json: { cartel_id: "cartel-1" },
      read_at: null as string | null,
      created_at: "2026-07-28T08:05:00Z",
    },
  ];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/v1", "");
    const method = request.method();
    if (path === "/auth/refresh") {
      await fulfill(route, { access_token: "realtime-e2e-token" });
      return;
    }
    if (path === "/auth/me") {
      await fulfill(route, {
        id: "user-1",
        email: "realtime@example.invalid",
        display_name: "Realtime Operator",
        locale: "en",
        email_verified: true,
        is_admin: false,
        is_moderator: false,
      });
      return;
    }
    if (path === "/profiles/me") {
      await fulfill(route, {
        id: "profile-1",
        user_id: "user-1",
        world_id: "world-1",
        city_id: "city-1",
        codename: "Realtime Operator",
      });
      return;
    }
    if (path === "/news") {
      await fulfill(route, [
        {
          id: "news-1",
          title: "Verified market movement",
          summary: "A district market snapshot has changed.",
          published_at: "2026-07-28T08:00:00Z",
          certainty: "verified",
        },
      ]);
      return;
    }
    if (path === "/realtime/events") {
      await fulfill(route, [
        {
          id: "event-1",
          world_id: "world-1",
          event_type: "market.snapshot.created",
          event_version: 1,
          audience_type: "city",
          channel: "city:city-1",
          payload_json: { tick_id: "tick-1" },
          created_at: "2026-07-28T08:00:00Z",
          expires_at: "2026-08-04T08:00:00Z",
        },
        {
          id: "event-2",
          world_id: "world-1",
          event_type: "notification.created",
          event_version: 1,
          audience_type: "player",
          channel: "player:profile-1",
          payload_json: { notification_id: notifications[1]?.id },
          created_at: "2026-07-28T08:05:00Z",
          expires_at: "2026-08-04T08:05:00Z",
        },
      ]);
      return;
    }
    if (path === "/notifications" && method === "GET") {
      await fulfill(route, notifications);
      return;
    }
    if (path === "/notifications/unread-count") {
      await fulfill(route, {
        unread_count: notifications.filter((item) => item.read_at === null)
          .length,
      });
      return;
    }
    if (
      path ===
        "/notifications/11111111-1111-4111-8111-111111111111/read" &&
      method === "POST"
    ) {
      notifications = notifications.map((item) =>
        item.id === "11111111-1111-4111-8111-111111111111"
          ? { ...item, read_at: "2026-07-28T08:10:00Z" }
          : item,
      );
      await fulfill(route, { message: "Notification marked as read." });
      return;
    }
    if (path === "/notifications/read-all" && method === "POST") {
      notifications = notifications.map((item) => ({
        ...item,
        read_at: item.read_at ?? "2026-07-28T08:11:00Z",
      }));
      await fulfill(route, { message: "All notifications marked as read." });
      return;
    }
    await fulfill(
      route,
      {
        error: { code: "e2e.unhandled", message: `${method} ${path}` },
        server_time: "2026-07-28T08:00:00Z",
      },
      404,
    );
  });
}

test("event feed and unread notifications reconcile through REST", async ({
  page,
}) => {
  await mockRealtimeUxApi(page);
  await page.goto("/news");

  await expect(
    page.getByRole("heading", { name: "Cologne news" }),
  ).toBeVisible();
  await expect(page.getByText("Market.snapshot.created")).toBeVisible();
  await expect(page.getByText("city:city-1")).toBeVisible();
  await expect(
    page.getByLabel("2 unread notifications"),
  ).toBeVisible();

  const warning = page.locator(".list-row").filter({
    has: page.getByText("Liquidity warning"),
  });
  await warning.getByRole("button", { name: "Mark read" }).click();
  await expect(
    warning.getByRole("button", { name: "Mark read" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("1 unread notifications")).toBeVisible();

  await page.getByRole("button", { name: "Mark all read" }).click();
  await expect(page.getByRole("button", { name: "Mark all read" })).toHaveCount(
    0,
  );
  await expect(page.locator(".nav-badge")).toHaveCount(0);
  expect(await seriousAccessibilityViolations(page)).toEqual([]);
});
