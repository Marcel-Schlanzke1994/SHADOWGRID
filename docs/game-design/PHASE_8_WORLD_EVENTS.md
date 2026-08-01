# Phase 8 — Versioned world events and administration

Phase 8 turns global and local disruptions into versioned, data-driven rules. Event
definitions are historical contracts; every activation copies one concrete configuration
into an immutable instance so later balancing changes cannot rewrite past results.

## First event catalogue

Version 1 contains the five required templates: port strike, technology boom, real-estate
crisis, data leak and financial audit. Definitions declare a default scope, duration and
integer effect configuration. Supported scopes are world, city, district, industry and
company. Supported effects change revenue, operating cost, demand, specialist salary,
real-estate value, reputation, investigation pressure, stock risk and contract probability.
Money and ratios remain integer cents or basis points.

Administrators may disable a definition for future activations without changing its
historical title, description, version or effect contract. A new balancing contract
therefore requires a new version rather than an in-place rewrite.

## Preview and lifecycle

An administrator first submits a preview. The server validates definition state, scope,
duration and all optional overrides, calculates the affected-company count and returns the
effective configuration without writing an instance. Activation requires a separate
idempotent command and stores the concrete configuration, schedule and audit record.

An instance is `scheduled`, `active`, `ended` or `cancelled`. The worker starts scheduled
instances and expires active instances using UTC timestamps. Both transitions are
idempotent, so retrying a worker period cannot emit duplicate transitions or effects.
Administrators can safely end a scheduled or active instance; repeating the same end command
returns the existing terminal state.

Every activation and end creates a durable realtime event. REST and PostgreSQL remain
authoritative; the existing authenticated WebSocket adapter delivers the notification
instead of introducing a second Socket.IO state path.

## Composition and reports

Applicable active instances are ordered by `(starts_at, id)`. Multiplier effects compose
sequentially using integer basis-point arithmetic, and delta effects add. Final values are
hard-clamped to documented bounds: multipliers from 2,500 to 30,000 basis points and bounded
integer deltas for reputation, investigation, stock risk and contract probability. This
stable order makes overlapping events deterministic across API and worker processes.

Economy ticks consume demand, revenue and cost modifiers. Specialist payroll consumes the
salary modifier. Immutable market and company reports store the full composed event input
and modifier snapshot, so later event expiry cannot change an earlier report.

## API, UI and verification

Canonical routes live under `/api/v1/world-events*` and administrator-only
`/api/v1/admin/world-events*`. The administration page covers loading, empty, error,
preview, confirmation, success and safe-end states. The command center shows active banners
and a readable event feed. Forms are labelled, keyboard operable and localized.

Migration `0010_world_events` passes a fresh upgrade, downgrade and drift cycle. Backend
tests cover preview-without-write, authorization, disabled definitions, bounds, overlap
order, scheduled start, expiry, repeated scheduling and report integration. Desktop and
mobile Playwright cover administration and player banners with Axe.
