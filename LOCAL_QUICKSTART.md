# SHADOWGRID local quickstart

SHADOWGRID automatically uses Docker Compose when Docker is available and otherwise uses
the zero-dependency SQLite mode with a local idempotent scheduler.

## Start in at most ten steps

1. Install Git, Node.js 22.16 or newer, pnpm 11 and Python 3.13 or newer.
2. Open PowerShell or a WSL/Linux shell in the repository root.
3. Windows setup:
   `powershell -ExecutionPolicy Bypass -File scripts/setup-local.ps1`
4. Windows start:
   `powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1`
5. WSL/Linux setup: `bash scripts/setup-local.sh`
6. WSL/Linux start: `bash scripts/start-local.sh`
7. Open the displayed web URL (`5173` for SQLite, normally `3000` for Compose).
8. Read local demo accounts from `.local/demo-credentials.txt`; scripts never print them.
9. Recheck at any time with `scripts/verify-local.ps1` or `bash scripts/verify-local.sh`.
10. Stop with `scripts/stop-local.ps1` or `bash scripts/stop-local.sh`.

Force a mode by passing `-Mode SQLite|Compose` in PowerShell or `sqlite|compose` as the
first shell argument. Compose also exposes Mailpit at `http://localhost:8025` and
Prometheus at `http://localhost:9090`.

## Safe reset

Reset deletes only the resolved local database or named Compose volumes and requires an
exact confirmation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/reset-local.ps1 -ConfirmReset RESET -Start
```

```bash
bash scripts/reset-local.sh auto RESET --start
```

Financial and audit rows in any non-local environment must never be reset this way.

## Troubleshooting

### Docker is missing

Use the automatic or explicit SQLite mode. The local worker runs the same idempotent due
application services without Redis. PostgreSQL/Redis/ARQ topology proof still requires
Docker Desktop or a Linux Docker installation.

### A port is already in use

Stop SHADOWGRID first. For SQLite, inspect `.local/run/*.stderr.log`; for Compose, run
`docker compose ps` and `docker compose logs --tail=200 api worker web`.

### API is healthy but timed systems do not move

Run the verification script. It checks the worker process/service independently from API
health. SQLite worker output is in `.local/run/worker.stdout.log`; Compose worker output is
available through `docker compose logs worker`.

### Migration or invariant verification fails

Preserve `.local/shadowgrid.db` and the logs. Do not hand-edit accounts, ownership or share
rows. Run `pnpm migrate` and `pnpm data:verify`; repair through a migration or domain
transaction.

### Mail is not delivered in SQLite mode

Messages remain retryable when Mailpit is absent. Use Compose mode for local Mailpit.
Production SMTP is configured only through secret storage and an explicit activation gate.

### A stale PID file blocks startup

The scripts remove a stale record when its process no longer exists. They refuse to stop a
reused PID whose command line does not match the recorded SHADOWGRID process.
