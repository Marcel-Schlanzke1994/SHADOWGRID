from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess  # nosec B404
import sys
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from shadowgrid.config import PROJECT_ROOT, get_settings
from shadowgrid.local_backups import backup_sqlite_database, restore_sqlite_database


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_database() -> Path:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise RuntimeError(
            "The autonomous local restore drill requires a SQLite DATABASE_URL. "
            "Use scripts/restore.ps1 against an isolated PostgreSQL target for the production drill."
        )
    path = Path(url.database)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    source = path.resolve()
    local_root = (PROJECT_ROOT / ".local").resolve()
    try:
        source.relative_to(local_root)
    except ValueError as exc:
        raise RuntimeError(f"Refusing restore drill source outside {local_root}") from exc
    return source


def main() -> None:
    source = _source_database()
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    backup = PROJECT_ROOT / "backups" / f"shadowgrid-{timestamp}-restore-drill.sqlite3"
    report_path = PROJECT_ROOT / ".project" / "restore-drill-result.json"
    original_digest = backup_sqlite_database(source, backup)

    local_root = PROJECT_ROOT / ".local"
    local_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="restore-drill-", dir=local_root) as temporary:
        temporary_root = Path(temporary).resolve()
        working = temporary_root / "working.sqlite3"
        safety = temporary_root / "pre-restore.sqlite3"
        backup_sqlite_database(source, working)
        with closing(sqlite3.connect(working)) as database:
            database.execute(
                "CREATE TABLE restore_drill_probe (id INTEGER PRIMARY KEY, marker TEXT NOT NULL)"
            )
            database.execute(
                "INSERT INTO restore_drill_probe (marker) VALUES (?)",
                ("must-disappear-after-restore",),
            )
            database.commit()

        restored_digest = restore_sqlite_database(backup, working, safety)
        with closing(sqlite3.connect(working)) as database:
            probe = database.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name = 'restore_drill_probe'"
            ).fetchone()
        if probe is not None:
            raise RuntimeError("Restore drill probe survived the restore.")
        if restored_digest != original_digest or _sha256(working) != original_digest:
            raise RuntimeError("Restored database digest differs from the verified backup.")

        environment = os.environ.copy()
        environment["DATABASE_URL"] = f"sqlite:///{working.as_posix()}"
        # The argv is constant and shell execution is never enabled.
        verification = subprocess.run(  # nosec B603
            [sys.executable, "-m", "shadowgrid.release_checks"],
            cwd=PROJECT_ROOT / "apps" / "api",
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if verification.returncode != 0:
            raise RuntimeError(
                "Post-restore data verification failed: "
                f"{verification.stdout.strip()} {verification.stderr.strip()}".strip()
            )

    result = {
        "completed_at": datetime.now(UTC).isoformat(),
        "mode": "isolated-local-sqlite",
        "source": str(source.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "backup": str(backup.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "backup_sha256": original_digest,
        "restored_sha256": restored_digest,
        "probe_removed": True,
        "post_restore_data_verify_exit_code": verification.returncode,
        "post_restore_data_verify_output": verification.stdout.strip(),
        "source_database_replaced": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(f"{json.dumps(result, indent=2)}\n", encoding="utf-8")
    print(
        "Restore drill passed: isolated restore, matching SHA-256 and "
        "post-restore data verification."
    )


if __name__ == "__main__":
    main()
