# SHADOWGRID – Architecture decisions

## 2026-07-19 — RUN 1 scope

- The repository was uninitialized, therefore the mandatory phase detector selected **RUN 1 – LOCAL FINAL**.
- `ALLOW_EXTERNAL_DEPLOY=true` is present, but external deployment belongs to RUN 2 and is not executed before local verification.
- The two “Projekt Netzwerke” PDFs are byte-different exports but have identical extracted text. Both were reviewed; neither contains additional requirements.
- Where the broad product vision and the explicit Season 0 MVP differ, the Master Goal's MVP floor is authoritative: eight districts, four configurable starter archetypes, five businesses, six facilities, eight specialist roles, five core operation categories and twelve world events.

## Architecture

- Monorepo: pnpm workspaces for React/Expo/shared TypeScript packages and a Python FastAPI service.
- API: FastAPI, Pydantic, SQLAlchemy and Alembic. PostgreSQL is the production/local-Compose database; SQLite is supported only for fast isolated tests.
- Worker: ARQ with Redis. Every scheduled task is idempotent and guarded against concurrent execution.
- Web: React, TypeScript, Vite, React Router, TanStack Query, Zustand (UI state only), Zod, Tailwind-compatible design tokens and accessible SVG/network alternatives.
- Mobile: Expo Router, React Native, TanStack Query and SecureStore; it consumes the generated shared API client.
- Server authority: balances, operation results, influence, investigation pressure, rankings and timers are persisted and resolved only by the API/worker.
- Integrity: all resource changes use an append-only ledger, idempotency keys and database transactions. Corrections are compensating entries.
- Time: UTC is stored and transmitted. Clients localize presentation only.
- Authentication: Argon2id passwords, short access tokens, rotating hashed refresh tokens, optional TOTP, explicit authorization dependencies and rate limiting.
- Localization: English is canonical, German is maintained, all configured locales fall back to English; `en-XA` and `ar-XB` exercise expansion and RTL.
- Safety: all organizations, cities and people are fictional. Covert and conflict operations are abstract categories and never provide actionable real-world criminal instructions.

## Version policy

- Runtime baselines are pinned to the locally verified Node 22.16.0 and a compatible Python 3.13 container line. Package-manager lockfiles are authoritative and production images use immutable version tags rather than `latest`.
- Dependencies are installed project-locally; missing system-wide Docker/Java/Android tools are reported by `scripts/check-environment.ps1` and are never installed with elevation automatically.

## Concurrency and dependency hardening

- Lazy operation resolution combines database row locks with an in-process serialization guard for SQLite/local two-device requests; the ARQ production worker uses locked, skip-locked selection.
- Organization role changes are director/permission controlled, protect the director role and create audit entries.
- Security overrides pin patched Vite, PostCSS and UUID versions until their Expo parents advance; React Router is pinned to its patched release. The final low-severity audit gate reports no known vulnerability.
- Root production builds are deliberately serialized so Metro and Vite do not exhaust constrained developer machines.
