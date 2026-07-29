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
| REQ-19 | Cross-platform one-click local lifecycle | PowerShell/Linux setup, start, stop, reset and verify scripts | Two real SQLite API/worker/web cycles plus syntax and script tests |
| REQ-23 | Localization truthfulness | 777-key English/German catalogs plus pseudo-locales | Parity validator and RTL E2E |
| REQ-26 | Complete player lifecycle | Ordered 30-step plan and cross-platform runner | API 33/33; Playwright 40 passed with two expected skips |

The generated OpenAPI contains 216 versioned paths. The required functional prefixes are
present for authentication, companies, economy, specialists, exchange, cartels,
intelligence, strategic actions, world events, seasons, contracts, loans, bonds, real
estate, events and notifications. Alembic forms one linear chain from `0001` through
`0017`.

## Explicit repository gaps

| ID | Gap | Evidence now | Required completion |
| --- | --- | --- | --- |
| REQ-18 | Privacy launch artifacts | Export/delete implementation exists | Retention, processor, incident and launch checklists |
| REQ-20 | Final restore drill | Verified SHA-256 backup exists | Safe restore and post-restore invariants |
| REQ-21 | Final operations automation | Health/build paths exist | Smoke scripts, season runbook proof and readiness report |
| REQ-24 | Complete asset library | 131/896 processed entries integrate | Process 765 pending and resolve one review item |
| REQ-25 | Multi-season balance evidence | Release-scale fixture passes | Deterministic simulation and three required reports |
| REQ-27 | Real store/marketing capture | Running UI and asset pipeline exist | Real captures and store readiness report |

## External or host-blocked requirements

| ID | Blocker | Repository-complete path | Final operator action |
| --- | --- | --- | --- |
| REQ-22 | EAS project/domains and signing credentials | Expo export, tests, config and store copy | Configure provider project, build signed AAB/IPA, submit with flag |
| REQ-28 | Docker/Mailpit unavailable and SMTP flag false | Mailer/account-flow code and tests | Run Mailpit after Docker install; activate provider only with flag |
| HOST-DOCKER-001 | Docker/PostgreSQL/Redis CLIs unavailable | SQLite release path fully green | Install Docker Desktop and execute Compose/worker/readiness checks |

These statuses are inputs to Phases 3–15. They are not release-completion claims.
