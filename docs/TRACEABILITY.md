# Master-goal traceability

This matrix maps the reviewed project briefs and Season 0 design document to the implemented RUN 1 deliverables and the verified RUN 2 Railway release. The two “Projekt Netzwerke” exports contain the same normalized text and were both reviewed.

| Requirement area | Implementation | Verification |
| --- | --- | --- |
| Production-oriented monorepo | `apps/api`, `apps/worker`, `apps/web`, `apps/mobile`, shared `packages/*`, pinned pnpm/Python dependencies | frozen lockfile, recursive type/lint/test/build gates |
| Server-authoritative economy | SQLAlchemy transactions, locked balances, append-only resource ledger, compensating entries and idempotency records | backend gameplay, duplicate-action and ledger reconciliation tests |
| Season 0 launch slice | Vesper world with 8 districts, 4 starter archetypes, 5 businesses, 6 facilities, 8 specialists, 5 abstract operations and 12 events | idempotent migration/seed plus browser critical-flow tests |
| Accounts and sessions | registration, verification, login, rotating refresh families, replay revocation, reset, logout, session management and optional TOTP | authentication integration tests and security threat model |
| Organizations and diplomacy | organizations, invites, treasury, member list/removal, protected director role, permission-based role changes and treaties | authorization/IDOR tests, audit records and web organization flow |
| Intelligence and investigations | uncertain intelligence, evidence, pressure, abstract investigations and non-procedural operation categories | API schemas/domain rules and seeded scenarios |
| Timed systems | ARQ jobs for due operations, facility/research completion, settlement and queued email; UTC throughout | worker type checks, idempotency guards and API integration tests |
| Web experience | React/Vite command center, city map with table alternative, businesses, operations, network with list alternative, organizations, rankings, news and settings | production build, Vitest, desktop/mobile Playwright and axe |
| Mobile experience | Expo Router shell for command, businesses, operations, organization and settings; SecureStore refresh tokens | Expo dependency check, Jest, TypeScript and 13-route static export |
| Localization | canonical English, reviewed German, 50 technical fallback locales and `en-XA`/`ar-XB` pseudo-locales | 198-key parity validator and RTL browser tests |
| Accessibility | semantic landmarks, skip/focus handling, labelled forms, status roles, text alternatives, reduced motion, high contrast and 44+ point mobile controls | component tests, axe critical-page checks, responsive/RTL E2E and accessibility checklist |
| Security and privacy | Argon2id, short bearer access tokens, hashed refresh tokens, CSP/security headers, CORS allowlist, request limits, explicit permissions, privacy export/delete and audit logs | Bandit, pip-audit, pnpm audit, secret-pattern scan and threat model |
| Operations and release | Dockerfiles, Compose, PostgreSQL, Redis, Mailpit, MinIO, Prometheus, Nginx, atomic Railway pre-deploy, supervised API/worker runtime, backups, CI and runbooks | GitHub container smoke, Railway deployment logs, public HTTPS/headers/readiness, live admin auth and production-world checks |

The broader long-term GDD remains a roadmap beyond the explicitly required Season 0 MVP floor. The separately authorized RUN 2 browser/API deployment is complete. Signed store submission and outbound SMTP delivery remain provider-account operations and are not claimed as completed.
