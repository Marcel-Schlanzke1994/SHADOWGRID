from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from shadowgrid.local_backups import backup_sqlite_database, restore_sqlite_database


def test_sqlite_backup_and_restore_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    safety = tmp_path / "safety.sqlite3"
    with closing(sqlite3.connect(source)) as database:
        database.execute("CREATE TABLE release_value (value INTEGER NOT NULL)")
        database.execute("INSERT INTO release_value (value) VALUES (1)")
        database.commit()

    original_digest = backup_sqlite_database(source, backup)
    with closing(sqlite3.connect(source)) as database:
        database.execute("UPDATE release_value SET value = 2")
        database.commit()

    restored_digest = restore_sqlite_database(backup, source, safety)

    with closing(sqlite3.connect(source)) as database:
        restored_value = database.execute("SELECT value FROM release_value").fetchone()
    with closing(sqlite3.connect(safety)) as database:
        safety_value = database.execute("SELECT value FROM release_value").fetchone()
    assert restored_value == (1,)
    assert safety_value == (2,)
    assert restored_digest == original_digest
