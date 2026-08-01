# Operations final readiness

Status: `repository_complete_external_infrastructure_pending`
Assessment date: 2026-07-30

## Repository and local evidence

| Gate | Evidence | Status |
| --- | --- | --- |
| Liveness/readiness | `/api/v1/health`, `/api/v1/ready`, API tests | complete |
| Request IDs and structured logs | middleware and auth-log privacy test | complete |
| API and worker supervision | production launcher plus eight ARQ functions | complete |
| Metrics access | public environments require a separate 32+ character Bearer token | complete |
| Alert definitions | seven validated definitions in `monitoring/alert-definitions.json` | complete |
| Backup verification | SQLite integrity check and SHA-256; PostgreSQL custom dump scripts | complete |
| Restore implementation | containment guard, confirmation token, safety backup, atomic SQLite replace | complete |
| Isolated restore drill | `.project/restore-drill-result.json` | complete after successful gate run |
| Season open/close | `pnpm test:season-runbook` | automated |
| Staging/production smoke | `scripts/smoke-test.mjs` and node tests | automated |
| Rollback | documented forward-repair and isolated-restore strategy | complete |

The local drill restores only a temporary database copy, removes a deliberately added
probe, compares the restored SHA-256 to the source backup and runs `pnpm data:verify`
against the restored copy. It never replaces the active local world.

Successful drill evidence:

- completed: `2026-07-30T00:45:41Z`;
- backup: `backups/shadowgrid-20260730-004515-673263-restore-drill.sqlite3`;
- source/restored SHA-256:
  `9ac309a811704f7457a9e524e19290e93dfcd5fec631912ba0e2a1b7922a8922`;
- restore probe removed: yes;
- post-restore `data:verify`: exit 0, `Release data invariants passed`;
- active source database replaced: no.

## External operator gates

The host has no Docker daemon, no local PostgreSQL client and no production-deployment
authorization. Therefore the following are correctly `blocked_external`:

- bind all seven alert definitions to the chosen provider and paging routes;
- configure the real `METRICS_TOKEN` in the secret store and monitoring client;
- run a PostgreSQL custom-dump restore into an isolated staging database;
- prove API and worker readiness against managed Redis/PostgreSQL;
- run authenticated staging smoke with an operator test account;
- perform production backup, deployment, post-deploy smoke and rollback observation.

No deployment was attempted because `FINALIZE_ALLOW_PRODUCTION_DEPLOY` is false.

## Exact operator sequence

```powershell
pnpm validate
powershell -ExecutionPolicy Bypass -File scripts/backup.ps1 -Label pre-deploy
# Restore the verified .dump into an isolated staging target:
powershell -ExecutionPolicy Bypass -File scripts/restore.ps1 `
  -Backup backups/shadowgrid-YYYYMMDD-HHMMSS-pre-deploy.dump `
  -ConfirmRestore RESTORE
pnpm data:verify
$env:STAGING_BASE_URL = "https://<staging-host>"
$env:SMOKE_EMAIL = "<staging-test-account>"
$env:SMOKE_PASSWORD = "<secret-store-value>"
pnpm smoke:staging
```

Only after those gates and explicit authorization:

```powershell
$env:FINALIZE_ALLOW_PRODUCTION_DEPLOY = "true"
$env:PRODUCTION_BASE_URL = "https://<production-host>"
pnpm smoke:production
```

Credentials, actual provider contacts and secret values must remain outside the repository.
