# Phase 1: authentication and Cologne onboarding

Phase 1 aligns the existing authentication system with the German-city roadmap.

## Authoritative flow

1. Registration validates email, display name, password and terms on the server.
2. Email verification enables login.
3. Login issues a short-lived access token and rotating opaque refresh session.
4. `GET /api/v1/world/cities` exposes active start cities. Season 0 currently exposes Köln.
5. `GET /api/v1/world/cities/{city_id}/districts` exposes Innenstadt, Hafenbezirk,
   Technologiepark, Gewerbering and Medienquartier.
6. `POST /api/v1/players/me/select-city` creates at most one profile per user and world.
   The request requires an `Idempotency-Key`.
7. Initial cash is configured as `STARTING_CASH_CENTS` and converted to exact decimal
   currency without a float. The default 8,000,000 cents produces €80,000.00.
8. Every initial resource is recorded through the append-only ledger before commit.

Changing the selected city or district after onboarding returns
`player.city_already_selected`. Repeating the original idempotent command returns the
existing profile without a second grant.

## Demo safety

`LOCAL_DEMO_MODE=true` enables deterministic local seed accounts. `Settings` forces demo
mode off for `production` and `staging`, even if an environment variable attempts to enable
it. The seed command refuses to run when demo mode is disabled.

## Compatibility

The previous `/worlds/{world_id}/join` and `/profiles/me` contracts remain available.
Roadmap clients should use `/world/cities`, `/players/me/select-city`, `/players/me` and
`/players/me/resources`.
