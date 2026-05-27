"""User accounts: auth lookup, OAuth provisioning, login lockout."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.db.connection import execute, fetch_one


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    return fetch_one("SELECT * FROM users WHERE username = ?", (username,))


def create_user(username: str, password_hash: str) -> None:
    execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash))


def get_user_by_google_id(google_id: str) -> Optional[sqlite3.Row]:
    return fetch_one("SELECT * FROM users WHERE google_id = ?", (google_id,))


def create_oauth_user(username: str, email: str, google_id: str) -> None:
    execute("INSERT INTO users (username, email, google_id) VALUES (?, ?, ?)",
            (username, email, google_id))


def is_account_locked(username: str) -> bool:
    if not username:
        return False
    row = fetch_one("SELECT locked_until FROM users WHERE username = ?", (username,))
    if not row or not row[0]:
        return False
    try:
        return datetime.fromisoformat(str(row[0])) > datetime.now()
    except Exception:
        return False


def record_failed_login(username: str, max_attempts: int = 5,
                        lock_minutes: int = 15) -> Dict[str, Any]:
    """Increment counter, lock at max_attempts. Returns {'locked': bool, 'attempts': int}."""
    if not username:
        return {"locked": False, "attempts": 0}
    row = fetch_one("SELECT failed_login_attempts FROM users WHERE username = ?", (username,))
    if not row:
        return {"locked": False, "attempts": 0}
    attempts = (row[0] or 0) + 1
    locked = attempts >= max_attempts
    locked_until = (datetime.now() + timedelta(minutes=lock_minutes)).isoformat() if locked else None
    execute(
        "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE username = ?",
        (attempts, locked_until, username),
    )
    return {"locked": locked, "attempts": attempts}


def record_successful_login(username: str) -> None:
    if not username:
        return
    execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL,"
        " last_login_at = CURRENT_TIMESTAMP WHERE username = ?",
        (username,),
    )
