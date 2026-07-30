# Testing strategy

- Backend: the full API/domain suite covers authentication and shared rate windows,
  authorization/IDOR, every economy vertical, concurrency, idempotency, immutable history,
  migrations, release invariants and backup scripts. Runtime coverage must remain at least
  65%.
- Web: Vitest covers reusable accessible UI, client reconciliation and locale formatting.
  The 58-scenario Playwright matrix covers Chromium desktop and Pixel 7 layouts, real
  login/navigation, all roadmap verticals, confirmation/error states, zoom, RTL and Axe.
  Two workers share one local API/Vite pair and assertions allow 15 seconds for a loaded
  state on constrained release hosts.
- Mobile: Jest enforces high-contrast tokens and 44-point controls with an 80% threshold;
  strict typecheck, lint and the 15-route Expo web export prove the package after dependency
  changes.
- Load: `tests/load/test_release_scale.py` creates 100 players, 500 companies and 10,000
  open exchange orders in a real SQLAlchemy database. It invokes the authoritative economy
  tick, indexed order-book query and ledger/share-backed match with explicit local ceilings.
  The smaller multiplayer and smoke profiles remain complementary checks.
- Security: Ruff, strict mypy, ESLint, Bandit, pip-audit, pnpm audit and a masked
  secret-pattern scan run together. The one documented React Router RSC advisory is ignored
  only because this project exposes no RSC/server-action surface.
- Release materials: `pnpm release:materials` validates repository-local Markdown targets,
  external URL syntax and production dependency license metadata. Known AGPL, SSPL, BUSL,
  Commons Clause, unlicensed and GPL-only records fail the gate. Dynamically linked LGPL and
  file-level MPL libraries are retained in the review report rather than silently discarded;
  the JSON evidence is written to `.project/release-materials-scan.json`.
- Assets: `pnpm assets:gate` is stricter than technical validation. Every required manifest
  entry must be approved and have source, production files, license metadata and, for real
  screenshots, functioning-application provenance. Pending, review-required, rejected or
  failed entries stop release.
- Final evidence: after committing the reviewed candidate, `pnpm release:final-run` requires
  a clean working tree, uses a new isolated SQLite database, executes every Phase 13 gate and
  writes command, exit-code, tool-version, log-hash, build-size, asset, balance and recovery
  evidence below `docs/release-evidence/final-release-<UTC timestamp>/`.
- Data and recovery: a clean migration plus seed is repeated for idempotency,
  `pnpm data:verify` checks persisted invariants, and backup/restore is verified before the
  restored database is checked again.

Run `pnpm validate` for the complete local release gate. It performs setup, migration/seed,
API generation, localization, formatting, lint, type checks, unit/integration/load/security
tests, production builds and Playwright. `make verify-release` is the equivalent convenience
target where GNU Make is installed.

`pnpm scan:secrets` can be repeated independently; `pnpm test:security` invokes the same
masked scan before Bandit and dependency audits.
