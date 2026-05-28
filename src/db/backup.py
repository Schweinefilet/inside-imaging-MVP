"""Database backup utilities."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.db.connection import DB_PATH


def backup_db(label: str = "") -> Optional[Path]:
    """Copy the live database to a timestamped file in the same directory.

    Creates at most one backup per calendar day (subsequent calls return the
    existing backup path). Pass a *label* to force a distinct backup (e.g.
    "pre_migration").

    Returns the backup path, or None if the database does not exist yet.
    """
    if not DB_PATH.exists():
        return None

    today = datetime.now().strftime("%Y%m%d")
    suffix = f".{label}" if label else ""
    backup_path = DB_PATH.parent / f"patient_data.{today}{suffix}.bak"

    if backup_path.exists() and not label:
        return backup_path  # already backed up today

    try:
        shutil.copy2(str(DB_PATH), str(backup_path))
        logging.info("Database backed up → %s", backup_path)
        return backup_path
    except Exception:
        logging.exception("Database backup failed")
        return None
