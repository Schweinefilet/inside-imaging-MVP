"""Database utilities for Inside Imaging.

Provides functions to initialize and interact with an SQLite database used
for storing patient encounter metadata and user accounts. Patient names are
truncated to protect privacy while retaining other details for statistics.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Optional
import hashlib
from datetime import datetime


DB_PATH = Path("data/patient_data.db")


def get_connection() -> sqlite3.Connection:
    """Return a new database connection (ensures foreign keys enabled)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create database tables if they do not already exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()
    # Table for patient encounters; no full names stored
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            truncated_name TEXT,
            age TEXT,
            sex TEXT,
            date TEXT,
            hospital TEXT,
            study TEXT,
            reason TEXT,
            technique TEXT,
            findings TEXT,
            conclusion TEXT,
            concern TEXT,
            language TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Ensure the language column exists for backward compatibility
    cur.execute("PRAGMA table_info(patients)")
    cols = [row[1] for row in cur.fetchall()]
    if 'language' not in cols:
        cur.execute("ALTER TABLE patients ADD COLUMN language TEXT")
    # Table for users
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def truncate_name(name: str) -> str:
    """Return a truncated version of a patient's name.

    This takes the first letter of each word and appends asterisks. If
    the name is empty, returns an empty string.
    """
    if not name:
        return ""
    parts = name.split()
    return " ".join(p[0] + "***" for p in parts)


def add_patient_record(data: Dict[str, str]) -> None:
    """Insert a patient encounter record into the database.

    The data dictionary should contain the keys: name, age, sex, date,
    hospital, study, reason, technique, findings, conclusion, concern,
    and language. The name will be truncated before being stored. If
    language is not provided, it will be stored as an empty string.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO patients (
            truncated_name, age, sex, date, hospital, study,
            reason, technique, findings, conclusion, concern, language
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            truncate_name(data.get("name", "")),
            data.get("age", ""),
            data.get("sex", ""),
            data.get("date", ""),
            data.get("hospital", ""),
            data.get("study", ""),
            data.get("reason", ""),
            data.get("technique", ""),
            data.get("findings", ""),
            data.get("conclusion", ""),
            data.get("concern", ""),
            data.get("language", ""),
        ),
    )
    conn.commit()
    conn.close()


def get_stats() -> Dict[str, int]:
    """Return aggregate statistics on stored patient encounters.

    Returns a dictionary with keys: total, male, female, and age range counts.
    Age ranges are grouped as: 0-17, 18-30, 31-50, 51-65, 66+.
    """
    conn = get_connection()
    cur = conn.cursor()
    # Overall counts
    cur.execute("SELECT COUNT(*) FROM patients")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM patients WHERE sex = 'M'")
    male = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM patients WHERE sex = 'F'")
    female = cur.fetchone()[0]
    # Age range counts
    cur.execute("SELECT age FROM patients WHERE age IS NOT NULL AND age != ''")
    ages = cur.fetchall()
    ranges = {"0-17": 0, "18-30": 0, "31-50": 0, "51-65": 0, "66+": 0}
    for row in ages:
        a = row[0]
        # attempt to parse the age as an integer; if fails, skip
        try:
            n = int(str(a).split()[0])
        except Exception:
            continue
        if n < 18:
            ranges["0-17"] += 1
        elif n <= 30:
            ranges["18-30"] += 1
        elif n <= 50:
            ranges["31-50"] += 1
        elif n <= 65:
            ranges["51-65"] += 1
        else:
            ranges["66+"] += 1
    conn.close()
    # Flatten the dictionary for ease of use in templates
    return {"total": total, "male": male, "female": female, **ranges}


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    """Retrieve a user by username (returns a Row or None)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(username: str, password_hash: str) -> None:
    """Create a new user with the given username and password hash."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    conn.commit()
    conn.close()