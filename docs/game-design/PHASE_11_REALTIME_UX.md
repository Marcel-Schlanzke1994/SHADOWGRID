# Phase 11 — Realtime delivery, notifications and resilient UX

Phase 11 adds an authenticated, versioned realtime adapter around SHADOWGRID's durable
server state. REST responses and PostgreSQL remain authoritative: WebSocket events only
notify clients which TanStack Query data must be reconciled. No ownership, balance, order
or company state exists exclusively in a socket payload.

## Protocol and audience isolation

The initial WebSocket message contains the access token, world identifier, protocol
version and optional durable event cursor. The server validates the session and derives
the player profile, city and active cartel itself. Clients cannot subscribe to arbitrary
rooms. An authenticated connection receives only:

- its world channel;
- its selected city channel;
- its private player channel;
- its active cartel channel, when applicable.

Every persisted event carries protocol version 1, a dotted lowercase event type, a bounded
JSON payload, an expiry time and an explicit `world`, `city`, `cartel` or `player`
audience. Database checks protect the audience shape and protocol range. A unique optional
deduplication key makes retrying worker and application-service emissions safe.

Disconnects use exponential backoff. The last delivered event ID is stored per world and
sent when reconnecting. The server verifies that the cursor is still visible to that
player before resuming in creation order. Expired events disappear from the feed, and an
invalid or inaccessible cursor is rejected without leaking whether a foreign event exists.

## Canonical events

The versioned protocol validates the required identifiers for:

`player.resources.updated`, `company.metrics.updated`,
`market.snapshot.created`, `exchange.order.updated`,
`exchange.trade.executed`, `cartel.invitation.created`,
`cartel.project.updated`, `world.event.started`, `world.event.ended`,
`notification.created` and `season.phase.changed`.

Company financial defaults additionally create private warnings. Legacy gameplay events
remain supported when they follow the same versioned dotted-name and payload-size rules.

## Notifications and client behaviour

Notifications are durable and scoped to the authenticated user. The API supports bounded
lists, unread-only filtering, unread counts, idempotent read-one and read-all commands.
Notification content is immutable; only `read_at` can change. The responsive News view
shows the durable event feed and notification history, while navigation exposes the unread
count. Loading, empty, error and success states remain accessible by keyboard and screen
reader.

The client maps known event types to narrow query-key invalidations and falls back to a
safe world refresh for unknown events. It never applies event payloads as authoritative
game state, so reconnects and multiple devices converge through REST.

## Verification

Migration `0016_realtime_notifications` passes a fresh upgrade, downgrade, re-upgrade and
schema-drift check. Backend tests cover payload contracts, deduplication, immutable events
and notifications, room isolation, foreign cursors, authenticated WebSocket delivery,
resume after reconnect, invalid handshakes, expiration and read ownership. Desktop and
mobile Playwright cover the live feed, unread badge, read-one/read-all reconciliation and
Axe accessibility.
