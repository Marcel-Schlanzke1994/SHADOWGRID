# Operations runbook

## Health and observability

- Liveness: `GET /api/v1/health`
- Readiness/database check: `GET /api/v1/ready`
- Prometheus metrics: `GET /metrics`
- Every API response includes `X-Request-ID` and `X-Server-Time`; structured logs repeat the request ID.
- Primary alerts: readiness failure, HTTP 5xx rate, p95 latency, worker retry/failure rate, Redis unavailability, database saturation and negative ledger reconciliation.

## Triage

1. Identify the affected world, user-safe pseudonymous ID, UTC time and request ID.
2. Check API/worker logs with `docker compose logs --tail=200 api worker`.
3. Check PostgreSQL and Redis health before restarting application processes.
4. For stuck due work, restore the worker and let idempotent jobs replay; do not manually alter resource balances.
5. For an economic discrepancy, compare `resource_balances` with the sum of `ledger_entries`, preserve evidence and ship a corrective ledger mutation.

## Maintenance and incidents

During planned maintenance, stop accepting state-changing traffic at the edge, allow in-flight requests to finish, pause the worker, back up, migrate, resume the worker and reopen traffic. For suspected account compromise revoke sessions through the account/admin workflow. For a secret compromise rotate provider secrets, redeploy, revoke refresh families and document affected time ranges.

## Season operations

Before opening a season, validate district/event seed data, snapshot the database, confirm timers in UTC and smoke-test all role personas. At season end, freeze new operations, resolve due jobs, compute rankings from server values, publish the snapshot and retain the world as read-only before starting the next world.
