"""User accounts: auth lookup, OAuth provisioning, login lockout."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.db.connection import execute, fetch_all, fetch_one


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


# --- Role management -----------------------------------------------------

def assign_role(username: str, role: str, assigned_by: str = "") -> None:
    execute(
        "INSERT OR IGNORE INTO user_roles (username, role, assigned_by) VALUES (?, ?, ?)",
        (username, role, assigned_by),
    )


def remove_role(username: str, role: str) -> None:
    execute("DELETE FROM user_roles WHERE username = ? AND role = ?", (username, role))


def get_user_roles(username: str) -> List[str]:
    rows = fetch_all("SELECT role FROM user_roles WHERE username = ?", (username,))
    return [str(row[0]) for row in rows]


def has_any_role(username: str, roles: List[str]) -> bool:
    if not username or not roles:
        return False
    placeholders = ",".join("?" * len(roles))
    row = fetch_one(
        f"SELECT 1 FROM user_roles WHERE username = ? AND role IN ({placeholders}) LIMIT 1",
        (username, *roles),
    )
    return row is not None


def get_all_users() -> List[Dict[str, Any]]:
    """Return all users with their roles and last login, ordered by username."""
    from src.db.connection import _format_timestamp
    rows = fetch_all(
        "SELECT username, email, last_login_at FROM users ORDER BY username"
    )
    result = []
    for row in rows:
        result.append({
            "username": row[0],
            "email": row[1] or "",
            "last_login_at": _format_timestamp(row[2]),
            "roles": get_user_roles(str(row[0])),
        })
    return result


# --- TOTP / MFA ----------------------------------------------------------

def get_totp_secret(username: str) -> Optional[str]:
    row = fetch_one("SELECT totp_secret FROM users WHERE username = ?", (username,))
    return str(row[0]) if row and row[0] else None


def is_totp_enabled(username: str) -> bool:
    row = fetch_one("SELECT totp_enabled FROM users WHERE username = ?", (username,))
    return bool(row and row[0])


def set_totp_secret(username: str, secret: str) -> None:
    execute("UPDATE users SET totp_secret = ? WHERE username = ?", (secret, username))


def enable_totp(username: str) -> None:
    execute("UPDATE users SET totp_enabled = 1 WHERE username = ?", (username,))


def disable_totp(username: str) -> None:
    execute("UPDATE users SET totp_enabled = 0, totp_secret = NULL WHERE username = ?", (username,))


# --- Radiologist specialty ---------------------------------------------------

VALID_SPECIALTIES = (
    "Neuroradiology", "Musculoskeletal", "Chest",
    "Abdominal", "Cardiovascular", "General",
)

# Maps specialty → default modality filter in the portal.
SPECIALTY_DEFAULT_MODALITY = {
    "Neuroradiology": "MRI",
    "Musculoskeletal": "MRI",
    "Chest": "CT",
    "Abdominal": "CT",
    "Cardiovascular": "CT",
    "General": "All",
}


def get_user_specialty(username: str) -> str:
    row = fetch_one("SELECT specialty FROM users WHERE username = ?", (username,))
    return str(row[0]) if row and row[0] else ""


def set_user_specialty(username: str, specialty: str) -> None:
    if specialty not in VALID_SPECIALTIES and specialty != "":
        raise ValueError(f"Invalid specialty: {specialty!r}")
    execute("UPDATE users SET specialty = ? WHERE username = ?", (specialty or None, username))
