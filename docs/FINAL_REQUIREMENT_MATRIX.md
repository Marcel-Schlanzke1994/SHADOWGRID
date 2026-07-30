# SHADOWGRID final requirement matrix

Run: `finalize-20260729T205043Z-9e706c8`

This document is the reader-facing companion to
`.project/final-requirement-matrix.json`. Statuses are deliberately limited to
`verified`, `gap` and `blocked_external`; no requirement is recorded as unknown,
assumed or silently untested.

## Implemented and currently verified

| ID | Requirement | Implementation and contract | Current proof |
| --- | --- | --- | --- |
| REQ-01 | Auth, verification, sessions, Cologne onboarding | Auth/onboarding services; `/api/v1/auth/*`, cities and player routes | Backend auth/onboarding plus desktop/mobile critical flow |
| REQ-02 | Private companies and ledger investments | Company/finance services; migration `0003` | Company tests and desktop/mobile company flow |
| REQ-03 | Authoritative economy | Economy/worker services; migration `0004` | Economy tests and 100-player/500-company load fixture |
| REQ-04 | Specialists and local AI | Specialist/AI services; migrations `0005`–`0006` | Backend suite and desktop/mobile specialist flow |
| REQ-05 | IPO, exchange, dividends | Exchange/finance services; migration `0007` | Supply/ledger invariants, scale match and E2E |
| REQ-06 | Cartels and district control | Cartel services; migration `0008` | Authorization/concurrency/ledger tests and E2E |
| REQ-07 | Intelligence and abstract PvP | Intelligence services; migration `0009` | Determinism/cooldown/trade tests and E2E |
| REQ-08 | Versioned world events | Event services/worker; migration `0010` | Lifecycle/composition tests and E2E |
| REQ-09 | Seasons and immutable archive | Season services/worker; migration `0011` | Ties/rewards/archive tests and admin/player E2E |
| REQ-10 | Tenders and contracts | Contract services; migration `0012` | Capacity/breach/season tests and E2E |
| REQ-11 | Company loans | Loan services; migration `0013` | Quote/payment/default tests and E2E |
| REQ-12 | Company bonds | Bond services; migration `0014` | Atomic settlement/default/maturity tests and E2E |
| REQ-13 | Real estate and headquarters | Real-estate services; migration `0015` | Purchase/lease/season tests and E2E |
| REQ-14 | Realtime and notifications | Durable event and client reconciliation; migration `0016` | Audience/cursor/read tests and E2E |
| REQ-15 | Release hardening | Rate limits, bounds, CORS, seed and invariant verifier; migration `0017` | Security, data and load gates |
| REQ-16 | Automated release gate | `pnpm validate` and Make alias | Exit 0: 107 backend, 12 web, 3 mobile, 4 load, 54 passed Playwright |
| REQ-17 | WCAG 2.2 AA local web gate | Shared accessible primitives and 31-page matrix | 62 desktop/mobile scans; focus, reduced motion and pseudo-locales passed |
| REQ-18 | Privacy launch engineering | Exact export, transactional pseudonymization, revocation and retention artifacts | Privacy/metrics/log tests plus legal and processor gates |
| REQ-19 | Cross-platform one-click local lifecycle | PowerShell/Linux setup, start, stop, reset and verify scripts | Two real SQLite API/worker/web cycles plus syntax and script tests |
| REQ-20 | Verified recovery drill | Isolated backup/restore runner and post-restore invariant verifier | SHA-256-identical restore; probe removed; data verifier exit 0 |
| REQ-21 | Operations automation | Protected metrics, machine-readable alerts, smoke and recovery scripts | Operations verifier, smoke tests, season runbook and restore drill passed |
| REQ-23 | Localization truthfulness | 777-key English/German catalogs plus pseudo-locales | Parity validator and RTL E2E |
| REQ-24 | Complete asset library | Resumable 896-entry catalog, provenance, visual reviews, production variants and Web/Mobile registries | 896/896 approved; validation, integration and asset release gate passed |
| REQ-25 | Multi-season balance evidence | Integer-only deterministic simulation and versioned config | 100 players, 500 companies, 10 cartels, four seasons; no critical exploit |
| REQ-26 | Complete player lifecycle | Ordered 30-step plan and cross-platform runner | API 33/33; Playwright 40 passed with two expected skips |
| REQ-27 | Real store/marketing capture | Functioning-app capture pipeline plus exact-size static and community art | 30/30 entries passed store gate; 20 real UI captures and complete visual review |

The generated OpenAPI contains 216 versioned paths. The required functional prefixes are
present for authentication, companies, economy, specialists, exchange, cartels,
intelligence, strategic actions, world events, seasons, contracts, loans, bonds, real
estate, events and notifications. Alembic forms one linear chain from `0001` through
`0017`.

## Explicit repository gaps

No repository requirement remains classified as `gap`. Release actions that require
external infrastructure, identities, credentials, legal ownership or explicit action flags
remain isolated below.

## External or host-blocked requirements

| ID | Blocker | Repository-complete path | Final operator action |
| --- | --- | --- | --- |
| REQ-22 | EAS project/account and signing credentials | Placeholder IDs/domains removed; 69-file all-platform preview, tests, verified config and store copy | Initialize real EAS project, device-test signed AAB/IPA, submit only with flag |
| REQ-28 | Docker/Mailpit unavailable and SMTP flag false | Localized mailer, complete account-flow tests, hardened SMTP validation and exact operator gate | Run Mailpit after Docker install; activate provider only with flag |
| HOST-DOCKER-001 | Docker/PostgreSQL/Redis CLIs unavailable | SQLite release path fully green | Install Docker Desktop and execute Compose/worker/readiness checks |

These statuses are inputs to Phases 3–15. They are not release-completion claims.
