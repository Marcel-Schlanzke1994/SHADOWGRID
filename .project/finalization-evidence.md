# SHADOWGRID finalization evidence

Run: `finalize-20260729T205043Z-9e706c8`

## Baseline

- Commit: `9e706c86b309ebb7d6a2e056b0104b30c876c1ef`
- Original branch: `main`
- Working branch: `codex/finalize-shadowgrid`
- Host: Windows PowerShell
- Node.js: `v24.14.0`
- pnpm: `11.9.0`
- Workspace dependency Python: `3.12.13`
- Project `.venv` Python used by release commands: `3.14.5`
- Docker CLI: unavailable
- PostgreSQL CLI: unavailable
- Redis CLI: unavailable

## Pre-finalization recovery point

- Command:
  `powershell -ExecutionPolicy Bypass -File scripts/backup.ps1 -Label pre-finalization`
- Result: verified SQLite backup
- File:
  `backups/shadowgrid-20260729-205043-913860-pre-finalization.sqlite3`
- SHA-256:
  `33fdc46aaadf4e0925191048edac56c19bdbe92ccfc06ab1ecc9552caa7edf6a`

## Source review

Read in full:

- finalization master prompt;
- `AGENTS.md`;
- canonical and compatibility architecture documents;
- `SHADOWGRID_SPEC.md`;
- Phase 1 through Phase 12 game-design contracts;
- traceability, release notes and release-candidate findings;
- testing, accessibility, security, privacy, deployment, operations, backup/restore,
  mobile release and translation-quality documents;
- complete asset-generation goal.

## Phase 0 static and asset checks

- `rg` marker scan: no source `TODO`, `FIXME`, `HACK` or `XXX`
- focused/disabled-test scan: no `.only`; three intentional mobile-project skips for the
  desktop-only 200% zoom assertion
- ignored-path verification: `.env`, `.local/**` and the backup are excluded from Git
- `pnpm assets:validate`: passed for every processed asset
- `pnpm assets:integration-test`: passed for every processed asset
- `pnpm assets:report`: reports refreshed

## Phase 1 local release gate

The unchanged `pnpm validate` command completed with exit code 0 on
`2026-07-29`:

- environment/setup, migration and seed: passed;
- release data invariants: passed;
- OpenAPI export and TypeScript client generation: passed;
- localization: 777 canonical English keys with complete German parity;
- formatting and lint: passed, 113 Python files formatted;
- strict typecheck: passed for all TypeScript workspaces and 61 Python source files;
- web unit tests: 12/12, 95.74% statements and 80% branches;
- mobile unit tests: 3/3, 100% on the tested theme module;
- backend tests: 107/107 in 1,701.55 seconds, 84.39% coverage;
- release-scale load tests: 4/4 in 36.89 seconds;
- secret scan, Bandit and `pip-audit`: no finding;
- `pnpm audit`: one documented ignored React Router RSC-only High advisory;
- Expo web export: 15 static routes;
- Vite build: 222 modules in 36.75 seconds;
- Playwright: 54 passed in 11.5 minutes, four intentional mobile-only zoom skips.

Docker/Compose, PostgreSQL and Redis could not be run because the host has none of those
CLIs. This prevents a valid API-plus-independent-worker Compose claim and is preserved as
`HOST-DOCKER-001`.

## Phase 2 requirement matrix

- Machine-readable requirements: 28
- Verified now: 17
- Explicit repository gaps: 9
- Explicit external blockers: 2
- Unknown, assumed or untested status values: 0
- Generated OpenAPI paths: 216
- Alembic migration chain: linear from `0001` through `0017`

## Phase 3 local one-click lifecycle

- Required PowerShell scripts: setup, start, stop, reset and verify
- Required Linux/WSL scripts: setup, start, stop, reset and verify
- PowerShell parser: all scripts passed
- Git Bash syntax parser: all shell scripts passed
- Real SQLite start/verify/stop cycles: two passed
- Started components: API, independent local due-job worker and Vite web
- API liveness and readiness: passed
- Web `/healthz`: passed
- Worker cycle: economy, AI, specialist market/payroll, mail, order expiry and all
  aggregate due resolvers executed
- Post-cycle release data invariants: passed
- Ruff/format: 111 backend/worker files passed
- mypy: 62 source files passed
- Release script tests: 5 passed

The local process controller records process identity and start time, refuses a reused PID
and stops the validated process tree. Reset requires the exact token `RESET` and confines
deletion to `.local/shadowgrid.db` or named Compose volumes.

WSL runtime and Compose execution remain part of `HOST-DOCKER-001` because this host has
neither an installed WSL distribution nor Docker.

## Phase 4 complete player lifecycle

- Machine-readable ordered plan: `scripts/lifecycle-plan.json`
- Required steps represented: 30/30
- Required personas represented: 7/7
- API lifecycle command: `pnpm test:lifecycle -- --api-only`
- API result: 33/33 passed in 548.53 seconds
- Browser lifecycle command: `pnpm test:lifecycle -- --e2e-only`
- Playwright result: 40 passed in 8.4 minutes
- Browser projects: Chromium desktop and Pixel 7 mobile viewport
- Expected skips: two mobile instances of the explicitly desktop-only 200% zoom test
- Failed, flaky or retried cases: zero
- Critical or serious Axe findings: zero

The API suite covers registration and real token verification, refresh rotation,
onboarding, every financial vertical, realtime reconciliation, all season phases, Hall of
Fame rewards, the next season and immutable history. Existing domain tests assert balanced
ledger transactions and fixed share supply at the relevant operations.

## Phase 5 UX and accessibility

- Primary routes reviewed: 31
- Route scans: 62 (Chromium desktop plus Pixel 7 mobile)
- Matrix result: 4/4 passed in 7.5 minutes
- Critical/Serious Axe findings after remediation: zero
- Shared Loading/Empty/Error/Success component tests: 12/12 passed
- Dialog-focus flow: 2/2 desktop/mobile passed
- Pseudo-locales: `en-XA` LTR and `ar-XB` RTL passed
- Reduced motion and skip-link target: passed
- Resolved findings: nested interactive Cologne SVG and prohibited unread-marker ARIA
- Final report: `docs/ACCESSIBILITY_FINAL_REPORT.md`

Physical NVDA/VoiceOver and signed iOS/Android touch exploration remain explicit operator
follow-ups because this host has no attached devices or signed provider artifacts.
