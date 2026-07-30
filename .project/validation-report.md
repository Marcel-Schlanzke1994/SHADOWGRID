# Validation report

Status: **Phase 12 release candidate passed** on 2026-07-28.

| Gate | Result |
| --- | --- |
| environment/setup | required Git, Node, pnpm and Python present; pnpm 11 install path verified; Docker/Java/ADB correctly reported optional |
| migration/seed/data | migration at head, repeat deterministic seed passed, Alembic reported no drift and `pnpm data:verify` passed |
| API/localization | OpenAPI TypeScript declarations regenerated; 777 English keys with complete German parity |
| formatting/lint | Prettier and Ruff format clean over both clients and 113 Python files; ESLint and Ruff clean |
| typecheck | all TypeScript workspaces clean; strict mypy clean across 61 Python source files |
| unit/integration | backend 107/107 at 84.38% coverage; web 12/12 at 95.74% statements and 80% branches; mobile 3/3 at 100% |
| load | 4/4 database-backed profiles in 78.90 seconds, including 100 players, 500 companies, 10,000 orders, tick and atomic match |
| security | no credential pattern, Bandit issue or known Python vulnerability; no reachable high-severity pnpm finding |
| production builds | Expo exported 15 routes; Vite transformed 222 modules with no circular manual-chunk warning |
| browser E2E | 54 passed, 4 intentional mobile-only zoom skips, 0 failed across Chromium desktop and Pixel 7 in 13.8 minutes |
| backup/restore | verified local SQLite backup/restore preserved SHA-256 `d3ca210de4409fc658899ae114dcbc5cca5282c9ab813f6987288a6e89fbabd1`; post-restore invariants passed |
| release workflow | `pnpm validate` exited 0; this is the exact command behind `make verify-release` |

GNU Make and Docker are not installed on the reviewed Windows host. The Make alias was
therefore not invoked literally, and PostgreSQL custom-dump execution remains a deployment
operation. Its scripts, containment checks and failure-safe restart paths are covered;
the zero-dependency local SQLite recovery path was executed end to end.

The final review strengthened the seed invariant to require the exact configured version
and random seed. Ruff, strict mypy, live `pnpm data:verify` and the complete backend gate
were repeated afterward; 107 tests passed at unchanged 84.38% coverage.

The prior Railway release remains documented historical evidence. This report does not
claim that the new local roadmap candidate was deployed, nor that signed mobile artifacts
or external SMTP credentials were created.
