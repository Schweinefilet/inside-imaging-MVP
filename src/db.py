"""Database utilities for Inside Imaging.

Provides functions to initialize and interact with an SQLite database used
for storing patient encounter metadata and user accounts. Patient names are
truncated to protect privacy while retaining other details for statistics.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Optional, Any, List
from collections import Counter
import re
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
            word_count INTEGER DEFAULT 0,
            disease_tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Ensure upgrade columns exist for older databases
    cur.execute("PRAGMA table_info(patients)")
    cols = [row[1] for row in cur.fetchall()]
    if "language" not in cols:
        cur.execute("ALTER TABLE patients ADD COLUMN language TEXT")
    if "word_count" not in cols:
        cur.execute("ALTER TABLE patients ADD COLUMN word_count INTEGER DEFAULT 0")
    if "disease_tags" not in cols:
        cur.execute("ALTER TABLE patients ADD COLUMN disease_tags TEXT")
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
    # Table for feedback/corrections from radiologists
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            feedback_type TEXT NOT NULL,
            subject TEXT NOT NULL,
            original_text TEXT,
            corrected_text TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by TEXT,
            admin_notes TEXT
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


def add_patient_record(data: Dict[str, Any]) -> int:
    """Insert a patient encounter record and return its new primary key."""
    conn = get_connection()
    cur = conn.cursor()
    disease_tags = data.get("disease_tags", [])
    if isinstance(disease_tags, (list, tuple)):
        disease_str = ",".join(sorted({tag.strip().lower() for tag in disease_tags if tag}))
    else:
        disease_str = str(disease_tags or "")

    try:
        word_count = int(data.get("word_count", 0) or 0)
    except Exception:
        word_count = 0

    cur.execute(
        """
        INSERT INTO patients (
            truncated_name, age, sex, date, hospital, study,
            reason, technique, findings, conclusion, concern, language,
            word_count, disease_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            word_count,
            disease_str,
        ),
    )
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return int(record_id)


def _parse_age(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    parts = re.findall(r"\d+", str(raw))
    if not parts:
        return None
    try:
        return int(parts[0])
    except Exception:
        return None


_DISEASE_KEYWORDS = {
    "oncology": ["tumor", "mass", "neoplasm", "malignan", "carcinoma"],
    "fracture": ["fracture", "break", "compression fracture"],
    "infection": ["infection", "abscess", "pneumonia", "sepsis"],
    "inflammation": ["inflamm", "itis", "colitis", "hepatitis"],
    "hemorrhage": ["hemorrhage", "bleed", "hematoma"],
    "degeneration": ["degeneration", "arthrosis", "arthritis", "sclerosis"],
    "vascular": ["aneurysm", "stenosis", "thrombus", "embol"],
    "normal": ["normal", "unremarkable", "no acute", "negative"],
}


def _detect_disease_tags(text: str) -> List[str]:
    low = (text or "").lower()
    tags = []
    for label, keywords in _DISEASE_KEYWORDS.items():
        if any(keyword in low for keyword in keywords):
            tags.append(label)
    if not tags:
        return ["general"]
    return sorted(set(tags))


def _format_tags_display(tags: List[str]) -> List[str]:
    return [t.replace("_", " ").strip().title() for t in tags if t]


def store_report_event(patient: Dict[str, Any], structured: Dict[str, Any], report_stats: Dict[str, Any], language: str) -> int:
    """Persist a summarized encounter for analytics without storing PHI."""
    text_blob = " ".join(
        filter(
            None,
            [
                structured.get("findings"),
                structured.get("conclusion"),
                structured.get("concern"),
            ],
        )
    )
    disease_tags = _detect_disease_tags(text_blob)

    record = {
        "name": patient.get("name", ""),
        "age": patient.get("age", ""),
        "sex": patient.get("sex", ""),
        "date": patient.get("date", ""),
        "hospital": patient.get("hospital", ""),
        "study": patient.get("study", ""),
        "reason": structured.get("reason", ""),
        "technique": structured.get("technique", ""),
        "findings": structured.get("findings", ""),
        "conclusion": structured.get("conclusion", ""),
        "concern": structured.get("concern", ""),
        "language": language,
        "word_count": report_stats.get("words", 0),
        "disease_tags": disease_tags,
    }
    return add_patient_record(record)


def _format_timestamp(raw: Optional[str]) -> str:
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(str(raw)).strftime("%b %d, %Y %H:%M")
    except Exception:
        return str(raw)


def get_stats() -> Dict[str, Any]:
    """Return aggregate statistics for dashboard and analytics views."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM patients")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM patients WHERE created_at >= datetime('now', '-30 day')")
    last_30 = cur.fetchone()[0]

    cur.execute("SELECT AVG(word_count) FROM patients WHERE word_count > 0")
    avg_words = cur.fetchone()[0] or 0

    cur.execute("SELECT sex, COUNT(*) FROM patients GROUP BY sex")
    gender_counts = {"male": 0, "female": 0, "other": 0}
    for sex, count in cur.fetchall():
        label = (sex or "").strip().upper()
        if label.startswith("M"):
            gender_counts["male"] += count
        elif label.startswith("F"):
            gender_counts["female"] += count
        else:
            gender_counts["other"] += count

    cur.execute("SELECT age FROM patients WHERE age IS NOT NULL AND age != ''")
    ranges = {"0-17": 0, "18-30": 0, "31-50": 0, "51-65": 0, "66+": 0}
    for (age_value,) in cur.fetchall():
        age = _parse_age(age_value)
        if age is None:
            continue
        if age < 18:
            ranges["0-17"] += 1
        elif age <= 30:
            ranges["18-30"] += 1
        elif age <= 50:
            ranges["31-50"] += 1
        elif age <= 65:
            ranges["51-65"] += 1
        else:
            ranges["66+"] += 1

    cur.execute(
        """
        SELECT language, COUNT(*) AS c
        FROM patients
        WHERE ifnull(language, '') != ''
        GROUP BY language
        ORDER BY c DESC
        """
    )
    language_mix = [{"label": row[0], "count": row[1]} for row in cur.fetchall()]

    cur.execute(
        """
        SELECT study, COUNT(*) AS c
        FROM patients
        WHERE ifnull(study, '') != ''
        GROUP BY study
        ORDER BY c DESC
        """
    )
    study_mix = [{"label": row[0], "count": row[1]} for row in cur.fetchall()]

    cur.execute("SELECT disease_tags FROM patients WHERE ifnull(disease_tags, '') != ''")
    disease_counter: Counter[str] = Counter()
    for (raw_tags,) in cur.fetchall():
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        disease_counter.update(tags)
    disease_mix = [
        {"label": label, "count": count}
        for label, count in disease_counter.most_common()
    ]

    cur.execute(
        """
        SELECT id, study, language, created_at, disease_tags
        FROM patients
        ORDER BY datetime(created_at) DESC
        LIMIT 6
        """
    )
    recent = []
    for report_id, study, language, created_at, tags in cur.fetchall():
        raw_tags = [t for t in (tags or "").split(",") if t]
        recent.append(
            {
                "id": report_id,
                "study": study or "Unknown",
                "language": language or "",
                "created_at": _format_timestamp(created_at),
                "disease_tags": _format_tags_display(raw_tags),
            }
        )

    # Get time series data for last 30 days
    cur.execute(
        """
        SELECT DATE(created_at) as report_date, COUNT(*) as count
        FROM patients
        WHERE created_at >= datetime('now', '-30 day')
        GROUP BY DATE(created_at)
        ORDER BY report_date ASC
        """
    )
    time_series_raw = {row[0]: row[1] for row in cur.fetchall()}
    
    # Fill in missing dates with zeros
    time_series = []
    from datetime import datetime, timedelta
    for i in range(30):
        date = datetime.now() - timedelta(days=29 - i)
        date_str = date.strftime('%Y-%m-%d')
        month_day = date.strftime('%m/%d')
        count = time_series_raw.get(date_str, 0)
        time_series.append({"label": month_day, "value": count})

    conn.close()

    return {
        "summary": {
            "total_reports": total,
            "last_30_days": last_30,
            "average_word_count": int(round(avg_words)) if avg_words else 0,
            "languages_tracked": len(language_mix),
        },
        "gender": gender_counts,
        "age_ranges": ranges,
        "languages": language_mix,
        "studies": study_mix,
        "diseases": disease_mix,
        "recent": recent,
        "time_series": time_series,
    }


def get_report_brief(report_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, study, language, created_at, disease_tags
        FROM patients
        WHERE id = ?
        """,
        (report_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    tags = [t for t in (row[4] or "").split(",") if t]
    return {
        "id": row[0],
        "study": row[1] or "Unknown",
        "language": row[2] or "",
        "created_at": _format_timestamp(row[3]),
        "disease_tags": _format_tags_display(tags),
    }


def get_report_detail(report_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, truncated_name, age, sex, date, hospital, study,
               reason, technique, findings, conclusion, concern,
               language, word_count, disease_tags, created_at
        FROM patients
        WHERE id = ?
        """,
        (report_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None

    disease_tags = [t for t in (row[14] or "").split(",") if t]

    patient = {
        "hospital": row[5] or "",
        "study": row[6] or "Unknown",
        "name": row[1] or "",
        "sex": row[3] or "",
        "age": row[2] or "",
        "date": row[4] or "",
        "history": "",
    }

    structured = {
        "reason": row[7] or "",
        "technique": row[8] or "",
        "findings": row[9] or "",
        "conclusion": row[10] or "",
        "concern": row[11] or "",
        "word_count": row[13] or 0,
        "comparison": "",
        "oral_contrast": "",
    }

    return {
        "id": row[0],
        "patient": patient,
        "structured": structured,
        "language": row[12] or "",
        "word_count": row[13] or 0,
    "disease_tags": _format_tags_display(disease_tags),
        "created_at": _format_timestamp(row[15]),
    }


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


def submit_feedback(username: str, feedback_type: str, subject: str, original: str = "", corrected: str = "", description: str = "") -> int:
    """Submit a new feedback/correction entry."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO feedback (username, feedback_type, subject, original_text, corrected_text, description, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (username, feedback_type, subject, original, corrected, description),
    )
    conn.commit()
    feedback_id = cur.lastrowid
    conn.close()
    return int(feedback_id)


def get_all_feedback(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all feedback submissions, optionally filtered by status."""
    conn = get_connection()
    cur = conn.cursor()
    if status:
        cur.execute(
            """
            SELECT id, username, feedback_type, subject, original_text, corrected_text, 
                   description, status, created_at, reviewed_at, reviewed_by, admin_notes
            FROM feedback
            WHERE status = ?
            ORDER BY created_at DESC
            """,
            (status,),
        )
    else:
        cur.execute(
            """
            SELECT id, username, feedback_type, subject, original_text, corrected_text, 
                   description, status, created_at, reviewed_at, reviewed_by, admin_notes
            FROM feedback
            ORDER BY created_at DESC
            """
        )
    rows = cur.fetchall()
    conn.close()
    
    feedback_list = []
    for row in rows:
        feedback_list.append({
            "id": row[0],
            "username": row[1],
            "feedback_type": row[2],
            "subject": row[3],
            "original_text": row[4] or "",
            "corrected_text": row[5] or "",
            "description": row[6] or "",
            "status": row[7],
            "created_at": _format_timestamp(row[8]),
            "reviewed_at": _format_timestamp(row[9]),
            "reviewed_by": row[10] or "",
            "admin_notes": row[11] or "",
        })
    return feedback_list


def update_feedback_status(feedback_id: int, status: str, reviewed_by: str, admin_notes: str = "") -> None:
    """Update the status of a feedback submission."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE feedback
        SET status = ?, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?, admin_notes = ?
        WHERE id = ?
        """,
        (status, reviewed_by, admin_notes, feedback_id),
    )
    conn.commit()
    conn.close()


def get_user_feedback(username: str) -> List[Dict[str, Any]]:
    """Retrieve all feedback submissions from a specific user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username, feedback_type, subject, original_text, corrected_text, 
               description, status, created_at, reviewed_at, reviewed_by, admin_notes
        FROM feedback
        WHERE username = ?
        ORDER BY created_at DESC
        """,
        (username,),
    )
    rows = cur.fetchall()
    conn.close()
    
    feedback_list = []
    for row in rows:
        feedback_list.append({
            "id": row[0],
            "username": row[1],
            "feedback_type": row[2],
            "subject": row[3],
            "original_text": row[4] or "",
            "corrected_text": row[5] or "",
            "description": row[6] or "",
            "status": row[7],
            "created_at": _format_timestamp(row[8]),
            "reviewed_at": _format_timestamp(row[9]),
            "reviewed_by": row[10] or "",
            "admin_notes": row[11] or "",
        })
    return feedback_list
