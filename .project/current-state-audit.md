# SHADOWGRID current-state audit

Run: `finalize-20260729T205043Z-9e706c8`

## Repository baseline

- Baseline commit: `9e706c86b309ebb7d6a2e056b0104b30c876c1ef`
- Original branch: `main`
- Protected working branch: `codex/finalize-shadowgrid`
- Baseline tree: modified, with 127 untracked non-ignored files
- Existing modified/untracked files are treated as user-owned implementation input
- Ignored secret/local-state paths verified: `.env`, `.local/**`, `backups/*.sqlite3`

The untracked set is materially release-critical: 95 files under `apps/`, 20 under
`docs/`, one load fixture, migrations `0003` through `0017`, API/domain modules and
Playwright scenarios. They must be validated and intentionally incorporated; they must not
be deleted or silently omitted.

## Host and toolchain

| Tool | Result |
| --- | --- |
| OS | Microsoft Windows 10.0.19045, AMD64 |
| Shell | PowerShell 7.6.3 |
| Git | 2.53.0.windows.3 |
| Node.js | 24.14.0 |
| pnpm | 11.9.0 |
| Workspace dependency Python | 3.12.13 |
| Project `.venv` Python | 3.14.5 |
| Expo CLI | 0.24.24 |
| GNU Make | unavailable |
| Docker CLI | unavailable |
| PostgreSQL CLI | unavailable |
| Redis CLI | unavailable |

The repository declares Node `>=22.16.0`, pnpm `11.1.3` and Python 3.13 in CI/mypy.
The installed Node version satisfies the declared range. The existing project virtual
environment uses Python 3.14.5 and passed the strict release gate; CI remains the required
Python 3.13 compatibility proof.

## Configuration and external authority

Local configuration files exist and are ignored. Only variable names were inventoried;
values were not printed. All required `FINALIZE_ALLOW_*` flags are absent, so every
external mutation remains prohibited:

- production deployment;
- Git push;
- Git tag;
- paid asset generation;
- store submission;
- production SMTP activation.

## Architecture and automation inventory

- Modular monorepo: `apps/api`, `apps/worker`, `apps/web`, `apps/mobile`, `packages/*`
- Runtime: FastAPI, ARQ, PostgreSQL/SQLite, Redis, React/Vite and Expo
- Containers: API and web Dockerfiles plus development/production Compose definitions
- CI: pull-request validation, container smoke on `main`, tagged container publication
- Release alias: `make verify-release` delegates to `pnpm validate`
- Local validation: `scripts/project.ps1`
- Recovery: verified PostgreSQL/SQLite backup and guarded restore scripts
- Asset pipeline: manifest, deterministic pipeline, geodata builder, validation,
  integration, optimization, contact-sheet and reporting commands

## Recovery point

The pre-finalization backup completed through the SQLite fallback:

- file:
  `backups/shadowgrid-20260729-205043-913860-pre-finalization.sqlite3`
- SHA-256:
  `33fdc46aaadf4e0925191048edac56c19bdbe92ccfc06ab1ecc9552caa7edf6a`

The file is ignored and recoverable through the guarded restore workflow.

## Static findings

- No `TODO`, `FIXME`, `HACK` or `XXX` marker was found in source; two `XXX`
  occurrences are dependency integrity hashes.
- No focused tests (`only`) or unconditional disabled unit test was found.
- Three Playwright tests intentionally skip the desktop-only 200% zoom assertion on the
  mobile project. The skip is scoped and documented.
- Legacy Flask/Celery/Socket.IO references occur only in architecture decision records
  explaining why the canonical FastAPI/ARQ stack is retained.
- A broad exploratory assignment scan identified known test fixtures and localization
  strings. The canonical masked release scanner, Bandit and both dependency audits passed;
  no secret or production-code finding was reported.
- Mobile configuration still contains the documented zero EAS project ID and
  `shadowgrid.example` associated-link hosts.

## Asset baseline

- Manifest entries: 896
- Approved: 130
- Review required: 1
- Pending: 765
- Rejected/failed: 0
- Recorded paid cost: EUR 0.00
- Processed-asset validation: passed
- Processed-asset integration validation: passed

The style lock is frozen and the approved processed set is technically consistent. The
library is not complete because most required manifest entries have not been processed.

## Phase-0 conclusion

The baseline is recoverable and sources are prioritized. Phase 0 can be verified after the
gap matrix, source map and masked security-scan classification are committed. Docker-based
evidence remains a host capability gap, not a reason to discard independent local work.
