# Backup and restore

PostgreSQL backups are compressed custom-format dumps stored under ignored `backups/`. Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup.ps1 -Label pre-release
```

The script creates the dump inside the database container's mounted backup directory and verifies its table of contents. Encrypt and copy verified dumps to storage outside the host. Recommended retention is 7 daily, 5 weekly and 12 monthly backups. Test restore at least monthly.

Restore is destructive and therefore requires an exact confirmation token and a source resolved inside `backups/`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore.ps1 -Backup backups/shadowgrid-YYYYMMDD-HHMMSS-pre-release.dump -ConfirmRestore RESTORE
```

The script verifies the dump, stops API/worker, restores with `--clean --if-exists`, then restarts services. After restore, run readiness, authentication, ledger reconciliation and one non-destructive world read before reopening traffic. Redis is rebuildable cache/queue state and is not a substitute for the PostgreSQL backup.
