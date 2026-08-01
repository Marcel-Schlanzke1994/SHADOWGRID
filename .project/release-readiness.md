# Release readiness

Status: **German-city roadmap release candidate passed** on 2026-07-28.

| Area | Status | Evidence |
| --- | --- | --- |
| Roadmap | Passed | Phases 0–12 are aligned in the gap analysis and traceability matrix |
| Bootstrap/data | Passed | Migration, repeated deterministic seed, Alembic drift check and persisted release invariants |
| Backend | Passed | 107 tests, 84.38% coverage, strict mypy over 61 source files |
| Web | Passed | 12 Vitest tests, 95.74% statement/80% branch coverage, 222-module production build |
| Mobile | Passed | 3 Jest tests at 100%, strict lint/typecheck and 15-route Expo export |
| Browser | Passed | 54 Playwright desktop/mobile scenarios; 4 intentional mobile-only desktop-zoom skips |
| Load | Passed | 100 players, 500 companies and 10,000 orders; real tick, query and atomic match in 78.90 seconds |
| Security | Passed | no Critical or unresolved High finding; secret scan, Bandit, pip-audit and reviewed pnpm gate passed |
| Recovery | Passed | verified local backup/restore preserved SHA-256 and post-restore invariants; PostgreSQL dump path retained |
| API/i18n | Passed | OpenAPI client regenerated; 777 canonical English keys with complete German parity |
| Full gate | Passed | `pnpm validate`, the exact command behind `make verify-release`, exited 0 |

The earlier Railway browser/API deployment remains historical evidence and was not
silently mutated by this local roadmap implementation. Promoting this candidate, signing
native store artifacts and configuring outbound transactional-email credentials remain
explicit external operator actions.
