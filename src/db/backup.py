"""Database backup utilities."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.db import connection as _conn_mod
from src.db.connection import get_connection


def backup_db(label: str = "") -> Optional[Path]:
    """Snapshot the live database to a timestamped file in the same directory.

    Creates at most one backup per calendar day (subsequent calls return the
    existing backup path). Pass a *label* to force a distinct backup (e.g.
    "pre_migration").

    Uses SQLite's online backup API rather than a raw file copy: the database
    runs in WAL mode, so recent commits can still be sitting in a separate
    -wal file — copying just the main file with shutil can silently produce a
    backup that's missing committed rows or is internally inconsistent.

    Reads DB_PATH/_DB_ENCRYPTION_KEY off the connection module at call time
    (not via `from ... import`) so this stays correct if DB_PATH is ever
    reassigned after import (e.g. test fixtures that redirect it).

    Returns the backup path, or None if the database does not exist yet.
    """
    db_path = _conn_mod.DB_PATH
    if not db_path.exists():
        return None

    today = datetime.now().strftime("%Y%m%d")
    suffix = f".{label}" if label else ""
    backup_path = db_path.parent / f"patient_data.{today}{suffix}.bak"

    if backup_path.exists() and not label:
        return backup_path  # already backed up today

    src_conn = None
    dst_conn = None
    try:
        src_conn = get_connection()
        if _conn_mod._DB_ENCRYPTION_KEY:
            dst_conn = _conn_mod._get_sqlcipher().connect(str(backup_path))
            dst_conn.execute(f"PRAGMA key=\"x'{_conn_mod._DB_ENCRYPTION_KEY}'\"")
        else:
            dst_conn = sqlite3.connect(str(backup_path))
        src_conn.backup(dst_conn)
        logging.info("Database backed up → %s", backup_path)
        return backup_path
    except Exception:
        logging.exception("Database backup failed")
        return None
    finally:
        if dst_conn is not None:
            dst_conn.close()
        if src_conn is not None:
            src_conn.close()
