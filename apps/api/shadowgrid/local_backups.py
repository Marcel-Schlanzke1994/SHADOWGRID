from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from shadowgrid.config import PROJECT_ROOT, get_settings

BACKUP_ROOT = (PROJECT_ROOT / "backups").resolve()
LOCAL_ROOT = (PROJECT_ROOT / ".local").resolve()


def backup_sqlite_database(source: Path, destination: Path) -> str:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise RuntimeError(f"SQLite source does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as source_db:
        with closing(sqlite3.connect(destination)) as destination_db:
            source_db.backup(destination_db)
    _verify_sqlite_database(destination)
    return _sha256(destination)


def restore_sqlite_database(
    backup: Path,
    destination: Path,
    safety_backup: Path,
) -> str:
    backup = backup.resolve()
    destination = destination.resolve()
    safety_backup = safety_backup.resolve()
    _verify_sqlite_database(backup)
    if destination.is_file():
        backup_sqlite_database(destination, safety_backup)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.restore")
    try:
        backup_sqlite_database(backup, temporary)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    _verify_sqlite_database(destination)
    return _sha256(destination)


def _verify_sqlite_database(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"SQLite database does not exist: {path}")
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as database:
        result = database.execute("PRAGMA integrity_check").fetchone()
    if result != ("ok",):
        raise RuntimeError(f"SQLite integrity check failed for {path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configured_sqlite_path() -> Path:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise RuntimeError("Local SQLite backup requires a sqlite DATABASE_URL")
    path = Path(url.database)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve()
    try:
        resolved.relative_to(LOCAL_ROOT)
    except ValueError as exc:
        raise RuntimeError(f"Refusing local restore outside {LOCAL_ROOT}") from exc
    return resolved


def _validated_backup_path(value: str) -> Path:
    resolved = Path(value).resolve()
    try:
        resolved.relative_to(BACKUP_ROOT)
    except ValueError as exc:
        raise RuntimeError(f"Backup must be inside {BACKUP_ROOT}") from exc
    if resolved.suffix != ".sqlite3":
        raise RuntimeError("SQLite backup must use the .sqlite3 extension")
    return resolved


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def main() -> None:
    parser = argparse.ArgumentParser(description="SHADOWGRID local SQLite backup and restore")
    subcommands = parser.add_subparsers(dest="command", required=True)
    backup_parser = subcommands.add_parser("backup")
    backup_parser.add_argument("--label", default="manual")
    restore_parser = subcommands.add_parser("restore")
    restore_parser.add_argument("--backup", required=True)
    restore_parser.add_argument("--confirm", required=True)
    args = parser.parse_args()

    database = _configured_sqlite_path()
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    if args.command == "backup":
        safe_label = re.sub(r"[^a-zA-Z0-9_-]", "-", str(args.label))
        destination = BACKUP_ROOT / (f"shadowgrid-{_timestamp()}-{safe_label}.sqlite3")
        digest = backup_sqlite_database(database, destination)
        print(f"Verified SQLite backup: {destination} sha256={digest}")
        return
    if args.confirm != "RESTORE":
        raise RuntimeError("Restore requires the exact RESTORE confirmation")
    backup = _validated_backup_path(str(args.backup))
    safety = BACKUP_ROOT / f"shadowgrid-{_timestamp()}-pre-restore.sqlite3"
    digest = restore_sqlite_database(backup, database, safety)
    print(f"SQLite restore completed from {backup}; safety backup={safety}; sha256={digest}")


if __name__ == "__main__":
    main()
