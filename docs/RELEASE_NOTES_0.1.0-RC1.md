# SHADOWGRID 0.1.0-rc.1

Release-candidate date: 2026-07-28.

This candidate completes the German-city roadmap from foundation through release
hardening. Cologne is locally playable as a persistent, server-authoritative multiplayer
economy and strategy game. The modular monolith remains deployable with PostgreSQL, Redis,
the independently runnable API/worker, React web client and Expo mobile shell.

## Included

- Account, onboarding and five Cologne start districts.
- Ledger-backed companies, hourly economy, specialists and deterministic local competitors.
- IPOs, fixed share supply, atomic price-time exchange, portfolios and dividends.
- Cartels, district influence, intelligence and abstract strategic PvP.
- Versioned world events, seasons, rankings, immutable archives and permanent rewards.
- Contracts, company loans, fixed-supply bonds, persistent property and headquarters.
- Authenticated durable realtime events, reconnect cursors and immutable notifications.
- Shared rate limits, strict input/CORS boundaries, persisted seed identity, release
  invariant checks, roadmap-scale load evidence and verified backup/restore.

## Security review

The Phase 12 audit found no Critical issue. Two High and six Medium findings were fixed;
all three Low findings were either fixed or explicitly accepted at the deployment network
boundary. The transitive Expo `tar` advisory is patched at 7.5.21. The remaining React
Router advisory concerns an RSC/server-action surface SHADOWGRID does not use and is
documented in the threat model.

## Recovery proof

On the zero-dependency local target, backup and restore preserved SHA-256
`d3ca210de4409fc658899ae114dcbc5cca5282c9ab813f6987288a6e89fbabd1`.
Post-restore ledger, ownership, share-supply, allocation, foreign-key and seed-version
checks passed. Deployment environments continue to use verified PostgreSQL custom dumps.

## Verified release gates

The complete `pnpm validate` workflow passed on the release-candidate source:

- clean dependency/setup, migration, deterministic seed and release data invariants;
- generated OpenAPI/TypeScript client and 777-key English/German localization parity;
- Prettier/Ruff formatting, ESLint/Ruff lint and strict TypeScript/mypy over 61 Python
  source files;
- 107 backend tests at 84.38% coverage, 12 web tests at 95.74% statement/80% branch
  coverage and 3 mobile tests at 100%;
- 4 database-backed load tests in 78.90 seconds;
- secret scan, Bandit, pip-audit and the reviewed pnpm high-severity gate;
- 15-route Expo export and a 222-module Vite production build without circular chunks;
- 54 Playwright scenarios passed and 4 intentional mobile-only zoom skips, with no failure,
  across Chromium desktop and Pixel 7 projects in 13.8 minutes.

GNU Make is not installed on the reviewed Windows host. `make verify-release` is an alias
for the exact `pnpm validate` command that passed. The final review then strengthened the
seed-contract invariant; its impacted Ruff, mypy, data-verification and complete 107-test
backend gates were repeated successfully.

## Operator notes

- Run `pnpm validate` (or `make verify-release` where GNU Make exists) before promotion.
- Run `pnpm data:verify` after every migration or restore.
- Restrict `/metrics` to the Prometheus/operator network.
- Keep `WEB_ORIGINS` explicit and HTTPS-only in staging/production.
- Signed mobile store artifacts and outbound transactional-email provider credentials
  remain external operator actions, not repository release artifacts.
