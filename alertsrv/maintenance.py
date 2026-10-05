from __future__ import annotations

import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path


def backup_database(database: str | Path, destination: str | Path) -> Path:
    """Create a consistent SQLite backup using SQLite's online backup API."""
    source_path = Path(database)
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(str(source_path))
    try:
        target = sqlite3.connect(str(destination_path))
        try:
            source.backup(target)
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.commit()
        finally:
            target.close()
    finally:
        source.close()
    return destination_path


def verify_database(database: str | Path) -> bool:
    """Run SQLite integrity checks and return True only for a clean database."""
    try:
        connection = sqlite3.connect(str(database))
    except sqlite3.DatabaseError:
        return False
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        return bool(result and result[0] == "ok")
    except sqlite3.DatabaseError:
        return False
    finally:
        connection.close()


def restore_database(backup: str | Path, database: str | Path) -> Path:
    """Restore a verified backup atomically through a temporary replacement."""
    backup_path = Path(backup)
    database_path = Path(database)
    if not verify_database(backup_path):
        raise ValueError("backup database failed integrity check")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_name(database_path.name + ".restore.tmp")
    shutil.copy2(backup_path, temporary)
    try:
        if not verify_database(temporary):
            raise ValueError("temporary restored database failed integrity check")
        temporary.replace(database_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return database_path


def timestamped_backup_path(directory: str | Path, prefix: str = "alerts") -> Path:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(directory) / f"{prefix}-{now}.db"
