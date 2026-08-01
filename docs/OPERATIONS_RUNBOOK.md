# Operations runbook

Production: <https://shadowgrid-production-be34.up.railway.app>

## Health and observability

- Liveness: `GET /api/v1/health`
- Readiness/database check: `GET /api/v1/ready`
- Prometheus metrics: `GET /metrics`. Local development permits the internal scrape.
  Staging and production require `Authorization: Bearer <METRICS_TOKEN>` and return 404
  without the separately generated 32+ character provider secret.
- Every API response includes `X-Request-ID` and `X-Server-Time`; structured logs repeat the request ID.
- Primary alerts are machine-readable in
  [`monitoring/alert-definitions.json`](../monitoring/alert-definitions.json): readiness,
  HTTP 5xx, p95 latency, worker, Redis, PostgreSQL and ledger reconciliation.
- Railway runtime logs must show both Uvicorn and `Starting worker for 8 functions`; a
  healthy API alone is insufficient for timed game systems.

## Triage

1. Identify the affected world, user-safe pseudonymous ID, UTC time and request ID.
2. Check API/worker logs with `docker compose logs --tail=200 api worker`.
3. Check PostgreSQL and Redis health before restarting application processes.
4. For stuck due work, restore the worker and let idempotent jobs replay; do not manually alter resource balances.
5. For an economic discrepancy, compare `resource_balances` with the sum of `ledger_entries`, preserve evidence and ship a corrective ledger mutation.
6. Treat `.local/production-admin.env` as a local password handoff: do not commit or paste it into tickets, and rotate the account password after first human login.
7. Inspect shared `rate_limit_buckets` when diagnosing login or exchange throttling; do not
   delete live buckets merely to bypass a caller's `Retry-After` window.

## Maintenance and incidents

During planned maintenance, stop accepting state-changing traffic at the edge, allow in-flight requests to finish, pause the worker, back up, migrate, resume the worker and reopen traffic. For suspected account compromise revoke sessions through the account/admin workflow. For a secret compromise rotate provider secrets, redeploy, revoke refresh families and document affected time ranges.

Before reopening traffic after migration or restore, run `pnpm data:verify`. A failure is a
release blocker: preserve the database and logs, do not hand-edit financial/share rows, and
repair through a migration or compensating domain transaction.

## Season operations

Before opening a season, validate district/event seed data, snapshot the database, confirm timers in UTC and smoke-test all role personas. At season end, freeze new operations, resolve due jobs, compute rankings from server values, publish the snapshot and retain the world as read-only before starting the next world.

The automated open/close drill is `pnpm test:season-runbook`. It verifies administrator
RBAC, phase simulation, deterministic tie handling, immutable snapshots, idempotent repeated
close, financial-history preservation, archive state, persistent rewards, scheduler replay
and idempotent creation of the next season.

## Worker recovery

1. Check the supervisor for both API and ARQ processes.
2. Run `arq apps.worker.worker.WorkerSettings --check` from the application image.
3. Check managed Redis availability and the ARQ health key.
4. Restart the worker only after Redis and PostgreSQL are ready.
5. Allow idempotent due jobs to replay; never edit timer, ledger, share or ownership rows.
6. Run `pnpm data:verify` and confirm the worker alert clears.

## Database recovery

1. Stop state-changing traffic and pause the worker.
2. Create and verify a fresh safety backup.
3. Restore only a verified dump through `scripts/restore.ps1`.
4. Run migrations only when the release manifest marks them rollback-compatible.
5. Run `pnpm data:verify`, readiness, authentication, world-read and logout smoke.
6. Resume the worker, then reopen traffic in stages.

## Ledger reconciliation

Run `pnpm data:verify` on a 15-minute operator schedule and after every migration, restore
or season transition. Any non-zero result is Critical: freeze mutations, preserve evidence,
keep the database intact and repair through a reviewed migration or compensating domain
transaction.

## Staging and production smoke

Both runners verify liveness, readiness, tracing headers, authentication, account access,
world listing, a safe world read and logout without printing credentials or tokens:

```powershell
$env:STAGING_BASE_URL = "https://staging.example.invalid"
$env:SMOKE_EMAIL = "<operator-provided>"
$env:SMOKE_PASSWORD = "<operator-provided>"
pnpm smoke:staging
```

Production execution is additionally blocked unless
`FINALIZE_ALLOW_PRODUCTION_DEPLOY=true`. Repository-only dry runs are:

```powershell
pnpm smoke:staging:dry-run
pnpm smoke:production:dry-run
```

## Rollback

Prefer forward repair for append-only finance migrations. Roll back application code only
when the database migration is explicitly backward-compatible. Otherwise stop traffic,
restore the verified pre-deploy backup into an isolated target, validate it, switch traffic
only after approval, and retain the failed database for investigation. Never run a
destructive downgrade against the sole production copy.
