# Backup and restore

PostgreSQL backups are compressed custom-format dumps stored under ignored `backups/`. Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup.ps1 -Label pre-release
```

The script creates the dump inside the database container's mounted backup directory and verifies its table of contents. Encrypt and copy verified dumps to storage outside the host. Recommended retention is 7 daily, 5 weekly and 12 monthly backups. Test restore at least monthly.

When Docker is unavailable and the configured database is the local `.local` SQLite
database, the same command creates an integrity-checked `.sqlite3` backup with a printed
SHA-256 digest. This fallback exists only for the zero-dependency local target; PostgreSQL
custom dumps remain the deployment backup format.

Restore is destructive and therefore requires an exact confirmation token and a source resolved inside `backups/`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore.ps1 -Backup backups/shadowgrid-YYYYMMDD-HHMMSS-pre-release.dump -ConfirmRestore RESTORE
```

The script verifies a PostgreSQL dump, stops API/worker, restores with
`--clean --if-exists`, then restarts services even when restore fails. A local SQLite
restore verifies the source, creates a timestamped pre-restore safety backup, restores
through a temporary database and atomically replaces the local file. Stop local API and
worker processes before invoking it. After either restore, run readiness, authentication,
`pnpm data:verify` and one non-destructive world read before reopening traffic. Redis is
rebuildable cache/queue state and is not a substitute for a database backup.
