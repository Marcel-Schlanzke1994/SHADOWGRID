# AGENTS.md — SHADOWGRID engineering contract

## Product and safety

SHADOWGRID is a fictional seasonal strategy, economy and organization MMO. Use only fictional places, people, companies and groups. Covert markets and conflicts stay abstract and non-graphic. Never add real criminal procedures, evasion advice, weapon acquisition, evidence destruction, real corruption targets or real trafficking routes.

## Repository architecture

- `apps/api`: FastAPI application, SQLAlchemy persistence, Alembic migrations and OpenAPI.
- `apps/worker`: ARQ jobs. Jobs call domain services; they do not duplicate game rules.
- `apps/web`: React PWA. It never computes authoritative economic/game outcomes.
- `apps/mobile`: Expo app using the same API client, types, localization and game configuration.
- `packages/api-client`: generated/typed HTTP and WebSocket client.
- `packages/shared-types`: cross-client transport types only.
- `packages/game-config`: public, non-authoritative display configuration.
- `packages/i18n`: canonical messages, fallbacks, RTL and validation.
- `packages/validation`: shared client validation that mirrors, but never replaces, server validation.
- `packages/ui-tokens`: accessible colors, spacing and typography.
- `infrastructure`: container, Railway, proxy, monitoring and backup assets.
- `tests`: cross-service E2E, load and security checks.

Allowed dependencies flow from apps to packages. Packages must not import apps. API domain services may depend on persistence and schemas; routers must call services instead of writing balances directly. The worker imports domain services from the API package. Web and mobile import the shared API client and never each other.

## Database and ledger rules

- PostgreSQL is canonical. SQLite may be used only by isolated tests.
- Every schema change requires a forward and rollback-capable Alembic migration.
- Store timestamps as UTC-aware values.
- Resource, treasury and business money changes must create append-only ledger entries in the same transaction.
- Ledger entries are never updated or deleted. Corrections use compensating entries.
- Resource creation and mutations require idempotency keys plus uniqueness constraints.
- Lock rows or use equivalent concurrency control for balances, treasury, purchases, operation slots, membership limits, treaty acceptance, upgrades and initial grants.
- No client-provided result, balance, score, probability roll or completion timestamp is authoritative.

## Security rules

- Never commit secrets, real credentials, private keys, demo passwords or signing material.
- Passwords use Argon2id. Refresh tokens are rotating and stored only as hashes.
- All object access is checked against the authenticated subject to prevent IDOR.
- Admin, moderation, treasury and organization permissions are enforced server-side and audited.
- Critical organization actions require recent reauthentication.
- Apply input validation, output encoding, request-size limits, rate limits, secure headers, a CORS allowlist and CSP.
- Do not log tokens, passwords, private intel, personal exports, IP addresses or secret configuration.
- Empty exception handlers and silently ignored errors are forbidden.

## Localization rules

- No visible component text is hardcoded. English message IDs are canonical.
- Maintain complete English and German catalogs. Other configured locales must safely fall back to English and report their review status honestly.
- Preserve ICU parameters, validate catalogs and sanitize translated content.
- Exercise both `en-XA` expansion and `ar-XB` RTL. Numbers, dates, durations and plurals use locale-aware formatters.

## UI and accessibility rules

- Target WCAG 2.2 AA: semantic elements, labels, keyboard access, visible focus, sufficient contrast, reduced motion and 44 px touch targets.
- Never communicate state by color alone. Dialogs manage focus and errors are programmatically associated with inputs.
- Every graph, map and chart has an equivalent accessible table/list.
- Support 320 px width and 200% zoom. Mobile screens show one primary decision, at most three warnings and no forced desktop tables.
- Include loading, empty, error, offline, unauthorized, maintenance and season-complete states.

## Commands

- Setup: `pnpm setup` or `./scripts/project.ps1 setup`
- Development: `pnpm dev` or `./scripts/project.ps1 dev`
- Migration/seed: `pnpm migrate`, `pnpm seed`
- Format/lint/typecheck: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`
- Tests: `pnpm test`, `pnpm test:e2e`, `pnpm test:security`, `pnpm test:load`
- Full acceptance: `pnpm validate` or `./scripts/project.ps1 validate`

## Definition of done

A task is not complete because code compiles. It is complete only when relevant backend, frontend and mobile effects are implemented; authorization and validation exist; state changes are audited; tests, accessibility, localization, security and documentation checks pass; and there are no critical findings.

Forbidden shortcuts include fake APIs, empty screens, uncontrolled client authority, hardcoded secrets or UI copy, direct balance updates, missing migrations, skipped red tests, critical `TODO` markers, mock production data and claims that machine translations were human-reviewed.

## Failure and release procedure

Reproduce failures with the smallest relevant test, fix the root cause, rerun that suite, then rerun the full validation gate. Do not weaken assertions to make a failure disappear. Document unavoidable non-critical limitations with evidence.

RUN 1 ends only after clean setup, migrations, deterministic seed, lint, typecheck, unit/integration/E2E/accessibility/security checks and production builds pass. RUN 2 starts only from a validated `local_verified` state, repeats the audits, validates backup/restore and production containers, and never deploys publicly unless the explicit deployment gate and credentials are present. Never delete existing production resources or change a domain implicitly.
