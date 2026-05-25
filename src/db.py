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
from datetime import datetime, timedelta

from src import config


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
            username TEXT,
            context TEXT,
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
    if "username" not in cols:
        cur.execute("ALTER TABLE patients ADD COLUMN username TEXT")
    if "context" not in cols:
        cur.execute("ALTER TABLE patients ADD COLUMN context TEXT")
    # Table for users
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            email TEXT UNIQUE,
            google_id TEXT UNIQUE
        )
        """
    )
    # Ensure upgrade columns exist for users table
    cur.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cur.fetchall()]
    if "email" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    
    if "google_id" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
    # password_hash should be nullable for OAuth users
    # SQLite doesn't support ALTER COLUMN, so we rely on the initial CREATE TABLE 
    # and the fact that we won't enforce NOT NULL in code for OAuth users.

    # Tenants — every DICOM record and audit event is scoped to one
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT UNIQUE NOT NULL,
            display_name TEXT,
            region TEXT,
            phi_mode TEXT DEFAULT 'passthrough',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "INSERT OR IGNORE INTO tenants (tenant_id, display_name) VALUES (?, ?)",
        (config.DEFAULT_TENANT_ID, config.DEFAULT_TENANT_NAME),
    )

    # Per-tenant hospital integration config (added idempotently below)
    cur.execute("PRAGMA table_info(tenants)")
    tenant_cols = [row[1] for row in cur.fetchall()]
    _tenant_migrations = [
        ("integration_webhook_url", "TEXT DEFAULT ''"),
        ("pacs_ae_title", "TEXT DEFAULT ''"),
        ("pacs_host", "TEXT DEFAULT ''"),
        ("pacs_port", "INTEGER DEFAULT 0"),
        ("our_ae_title", "TEXT DEFAULT 'INSIDEIMG'"),
        ("return_path", "TEXT DEFAULT 'webhook'"),
        ("hospital_branding", "TEXT DEFAULT ''"),
    ]
    for col, ddl in _tenant_migrations:
        if col not in tenant_cols:
            cur.execute(f"ALTER TABLE tenants ADD COLUMN {col} {ddl}")

    # API keys for hospital systems calling our integration endpoints
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            key_hash TEXT UNIQUE NOT NULL,
            label TEXT,
            revoked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apikey_hash ON integration_api_keys(key_hash)")

    # Reports received via integration endpoints (HTTP or HL7)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS integration_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            source TEXT NOT NULL,
            source_ref TEXT,
            accession_number TEXT,
            patient_id_truncated TEXT,
            study_uid TEXT,
            status TEXT DEFAULT 'received',
            inbound_storage_key TEXT,
            outbound_pdf_key TEXT,
            language TEXT DEFAULT 'English',
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ireports_tenant_time ON integration_reports(tenant_id, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ireports_accession ON integration_reports(accession_number)")

    # Audit log — every PHI read/write hooks into this
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dicom_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            username TEXT,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_uid TEXT,
            ip_address TEXT,
            user_agent TEXT,
            outcome TEXT DEFAULT 'success',
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON dicom_audit(tenant_id, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_resource ON dicom_audit(resource_uid)")

    # DICOM study/series/instance hierarchy for PACS layer
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dicom_studies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_instance_uid TEXT UNIQUE NOT NULL,
            patient_name_truncated TEXT,
            patient_id TEXT,
            study_date TEXT,
            modality TEXT,
            study_description TEXT,
            accession_number TEXT,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dicom_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_instance_uid TEXT UNIQUE NOT NULL,
            study_instance_uid TEXT NOT NULL,
            series_number INTEGER,
            series_description TEXT,
            modality TEXT,
            num_instances INTEGER DEFAULT 0,
            FOREIGN KEY (study_instance_uid) REFERENCES dicom_studies(study_instance_uid)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dicom_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sop_instance_uid TEXT UNIQUE NOT NULL,
            series_instance_uid TEXT NOT NULL,
            instance_number INTEGER,
            rows INTEGER,
            columns INTEGER,
            s3_key TEXT NOT NULL,
            FOREIGN KEY (series_instance_uid) REFERENCES dicom_series(series_instance_uid)
        )
        """
    )

    # Idempotent migrations: add tenant_id and storage_key to existing DICOM rows
    for table in ("dicom_studies", "dicom_series", "dicom_instances"):
        cur.execute(f"PRAGMA table_info({table})")
        existing = [row[1] for row in cur.fetchall()]
        if "tenant_id" not in existing:
            cur.execute(
                f"ALTER TABLE {table} ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '{config.DEFAULT_TENANT_ID}'"
            )

    cur.execute("PRAGMA table_info(dicom_instances)")
    inst_cols = [row[1] for row in cur.fetchall()]
    if "storage_backend" not in inst_cols:
        cur.execute("ALTER TABLE dicom_instances ADD COLUMN storage_backend TEXT DEFAULT 's3'")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_studies_tenant ON dicom_studies(tenant_id, username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_series_tenant ON dicom_series(tenant_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_instances_tenant ON dicom_instances(tenant_id)")

    # Add tenant_id to users (default tenant for existing rows)
    cur.execute("PRAGMA table_info(users)")
    user_cols_v2 = [row[1] for row in cur.fetchall()]
    if "tenant_id" not in user_cols_v2:
        cur.execute(
            f"ALTER TABLE users ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '{config.DEFAULT_TENANT_ID}'"
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
            word_count, disease_tags, username, context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get("username", ""),
            data.get("context", ""),
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
    "oncology": ["tumor", "mass", "neoplasm", "malignan", "carcinoma", "metastasis", "lymphadenopathy", "nodule"],
    "fracture": ["fracture", "break", "compression fracture", "dislocation", "subluxation"],
    "infection": ["infection", "abscess", "pneumonia", "sepsis", "consolidation", "infiltrate", "bronchitis"],
    "inflammation": ["inflamm", "itis", "colitis", "hepatitis", "diverticulitis", "pancreatitis"],
    "hemorrhage": ["hemorrhage", "bleed", "hematoma", "contusion"],
    "degeneration": ["degeneration", "arthrosis", "arthritis", "sclerosis", "spondylosis", "fibrosis", "stenosis", "osteophytes"],
    "vascular": ["aneurysm", "stenosis", "thrombus", "embol", "infarct", "ischemia", "calcification"],
    "lung_disease": ["copd", "emphysema", "bronchiectasis", "bullae", "bulla", "effusion", "pneumothorax", "air pocket"],
    "normal": ["normal", "unremarkable", "no acute", "negative", "clear", "intact"],
}

def normalize_study_name(study: str) -> str:
    """Normalize raw study names into professional medical language for statistics."""
    if not study or study.lower() == "unknown":
        return "Unknown"
    
    low = study.lower()
    
    # Modality detection
    modality = ""
    if "mri" in low:
        modality = "MRI"
    elif "ct" in low or "computed tomography" in low:
        modality = "CT"
    elif "x-ray" in low or "plain film" in low or "radiograph" in low:
        modality = "X-ray"
    elif "ultrasound" in low or "usg" in low:
        modality = "Ultrasound"
    elif "mammogram" in low:
        modality = "Mammogram"
    elif "pet" in low:
        modality = "PET/CT"
    
    if not modality:
        return study.title() # Fallback for unique entries
        
    # Contrast detection
    contrast = ""
    if "without contrast" in low or "non-contrast" in low or "without dye" in low:
        contrast = " (non-contrast)"
    elif "with contrast" in low or "with iv contrast" in low or "with dye" in low:
        contrast = " (with contrast)"
        
    # Region detection
    region = ""
    has_abdomen = "abdomen" in low or "abdominal" in low or "tummy" in low or "belly" in low
    has_pelvis = "pelvis" in low or "pelvic" in low
    
    if "head" in low or "brain" in low:
        region = "Head"
    elif "chest" in low and (has_abdomen or has_pelvis):
        region = "Chest/Abdomen/Pelvis"
    elif "chest" in low:
        region = "Chest"
    elif has_abdomen and has_pelvis:
        region = "Abdomen/Pelvis"
    elif has_abdomen:
        region = "Abdomen"
    elif has_pelvis:
        region = "Pelvis"
    elif "kub" in low:
        region = "KUB"
    elif "urogram" in low:
        region = "Urogram"
    elif "spine" in low:
        if "cervical" in low:
            region = "Cervical Spine"
        elif "thoracic" in low:
            region = "Thoracic Spine"
        elif "lumbar" in low or "lumbosacral" in low:
            region = "Lumbar Spine"
        else:
            region = "Spine"
    elif "foot" in low:
        region = "Foot"
    elif "knee" in low:
        region = "Knee"
    elif "shoulder" in low:
        region = "Shoulder"
    
    if region:
        return f"{modality} {region}{contrast}"
    return f"{modality}{contrast}"


def detect_disease_tags(text: str) -> List[str]:
    low = (text or "").lower()
    tags = []
    for label, keywords in _DISEASE_KEYWORDS.items():
        if any(keyword in low for keyword in keywords):
            tags.append(label)
    
    # If other tags exist, remove 'normal' if present
    if "normal" in tags and len(tags) > 1:
        tags.remove("normal")
        
    if not tags:
        return ["general"]
    return sorted(set(tags))


def _format_tags_display(tags: List[str]) -> List[str]:
    return [t.replace("_", " ").strip().title() for t in tags if t]


def store_report_event(patient: Dict[str, Any], structured: Dict[str, Any], report_stats: Dict[str, Any], language: str, username: str = "", context: str = "") -> int:
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
    disease_tags = detect_disease_tags(text_blob)

    record = {
        "name": patient.get("name", ""),
        "age": patient.get("age", ""),
        "sex": patient.get("sex", ""),
        "date": patient.get("date", ""),
        "hospital": patient.get("hospital", ""),
        "study": normalize_study_name(patient.get("study", "")),
        "reason": structured.get("reason", ""),
        "technique": structured.get("technique", ""),
        "findings": structured.get("findings", ""),
        "conclusion": structured.get("conclusion", ""),
        "concern": structured.get("concern", ""),
        "language": language,
        "word_count": report_stats.get("words", 0),
        "disease_tags": disease_tags,
        "username": username,
        "context": context,
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
    study_counts: Counter[str] = Counter()
    for study_raw, count in cur.fetchall():
        normalized = normalize_study_name(study_raw)
        study_counts[normalized] += count
    
    study_mix = [
        {"label": label, "count": count}
        for label, count in study_counts.most_common()
    ]

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


def get_user_by_google_id(google_id: str) -> Optional[sqlite3.Row]:
    """Retrieve a user by their Google ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
    row = cur.fetchone()
    conn.close()
    return row


def create_oauth_user(username: str, email: str, google_id: str) -> None:
    """Create a new user via OAuth."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, email, google_id) VALUES (?, ?, ?)",
        (username, email, google_id),
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


def get_user_reports(username: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve recent reports for a specific user."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, study, language, created_at, disease_tags, truncated_name
        FROM patients
        WHERE username = ?
        ORDER BY datetime(created_at) DESC
        LIMIT ?
        """,
        (username, limit),
    )
    rows = cur.fetchall()
    conn.close()
    
    reports = []
    for row in rows:
        tags = [t for t in (row[4] or "").split(",") if t]
        reports.append({
            "id": row[0],
            "study": row[1] or "Unknown Study",
            "language": row[2] or "English",
            "created_at": _format_timestamp(row[3]),
            "disease_tags": _format_tags_display(tags),
            "patient_name": row[5] or "Patient",
        })
    return reports


def get_user_tenant(username: str) -> str:
    if not username:
        return config.DEFAULT_TENANT_ID
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT tenant_id FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return config.DEFAULT_TENANT_ID
    return str(row[0])


def get_tenant(tenant_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT tenant_id, display_name, region, phi_mode, created_at FROM tenants WHERE tenant_id = ?",
        (tenant_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "tenant_id": row[0],
        "display_name": row[1] or "",
        "region": row[2] or "",
        "phi_mode": row[3] or "passthrough",
        "created_at": _format_timestamp(row[4]),
    }


def create_tenant(tenant_id: str, display_name: str = "", region: str = "", phi_mode: str = "passthrough") -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO tenants (tenant_id, display_name, region, phi_mode) VALUES (?, ?, ?, ?)",
        (tenant_id, display_name, region, phi_mode),
    )
    conn.commit()
    conn.close()


def log_audit_event(
    tenant_id: str,
    username: str,
    action: str,
    resource_type: str = "",
    resource_uid: str = "",
    ip_address: str = "",
    user_agent: str = "",
    outcome: str = "success",
    details: str = "",
) -> int:
    if not config.AUDIT_LOG_ENABLED:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO dicom_audit (
            tenant_id, username, action, resource_type, resource_uid,
            ip_address, user_agent, outcome, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_id or config.DEFAULT_TENANT_ID,
            username or "",
            action,
            resource_type,
            resource_uid,
            ip_address,
            user_agent,
            outcome,
            details,
        ),
    )
    conn.commit()
    audit_id = cur.lastrowid
    conn.close()
    return int(audit_id)


def get_audit_log(tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, tenant_id, username, action, resource_type, resource_uid,
               ip_address, user_agent, outcome, details, created_at
        FROM dicom_audit
        WHERE tenant_id = ?
        ORDER BY datetime(created_at) DESC
        LIMIT ?
        """,
        (tenant_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "tenant_id": r[1], "username": r[2] or "",
            "action": r[3], "resource_type": r[4] or "", "resource_uid": r[5] or "",
            "ip_address": r[6] or "", "user_agent": r[7] or "",
            "outcome": r[8] or "", "details": r[9] or "",
            "created_at": _format_timestamp(r[10]),
        }
        for r in rows
    ]


def upsert_dicom_study(data: Dict[str, Any]) -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO dicom_studies (
            study_instance_uid, patient_name_truncated, patient_id, study_date,
            modality, study_description, accession_number, username, tenant_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("study_uid", ""),
            data.get("patient_name_truncated", ""),
            data.get("patient_id", ""),
            data.get("study_date", ""),
            data.get("modality", ""),
            data.get("study_description", ""),
            data.get("accession_number", ""),
            data.get("username", ""),
            data.get("tenant_id", config.DEFAULT_TENANT_ID),
        ),
    )
    conn.commit()
    conn.close()
    return str(data.get("study_uid", ""))


def upsert_dicom_series(data: Dict[str, Any]) -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO dicom_series (
            series_instance_uid, study_instance_uid, series_number,
            series_description, modality, num_instances, tenant_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("series_uid", ""),
            data.get("study_uid", ""),
            data.get("series_number", 0) or 0,
            data.get("series_description", ""),
            data.get("modality", ""),
            0,
            data.get("tenant_id", config.DEFAULT_TENANT_ID),
        ),
    )
    cur.execute(
        "UPDATE dicom_series SET num_instances = num_instances + 1 WHERE series_instance_uid = ?",
        (data.get("series_uid", ""),),
    )
    conn.commit()
    conn.close()
    return str(data.get("series_uid", ""))


def insert_dicom_instance(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO dicom_instances (
            sop_instance_uid, series_instance_uid, instance_number,
            rows, columns, s3_key, tenant_id, storage_backend
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("sop_uid", ""),
            data.get("series_uid", ""),
            data.get("instance_number", 0) or 0,
            data.get("rows", 0) or 0,
            data.get("columns", 0) or 0,
            data.get("s3_key", ""),
            data.get("tenant_id", config.DEFAULT_TENANT_ID),
            data.get("storage_backend", config.STORAGE_BACKEND),
        ),
    )
    conn.commit()
    instance_id = cur.lastrowid
    conn.close()
    return int(instance_id)


def get_dicom_studies(tenant_id: str, username: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    if username:
        cur.execute(
            """
            SELECT study_instance_uid, patient_name_truncated, patient_id, study_date,
                   modality, study_description, accession_number, username, created_at, tenant_id
            FROM dicom_studies
            WHERE tenant_id = ? AND username = ?
            ORDER BY datetime(created_at) DESC
            """,
            (tenant_id, username),
        )
    else:
        cur.execute(
            """
            SELECT study_instance_uid, patient_name_truncated, patient_id, study_date,
                   modality, study_description, accession_number, username, created_at, tenant_id
            FROM dicom_studies
            WHERE tenant_id = ?
            ORDER BY datetime(created_at) DESC
            """,
            (tenant_id,),
        )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "study_instance_uid": row[0],
            "patient_name_truncated": row[1] or "",
            "patient_id": row[2] or "",
            "study_date": row[3] or "",
            "modality": row[4] or "",
            "study_description": row[5] or "",
            "accession_number": row[6] or "",
            "username": row[7] or "",
            "created_at": _format_timestamp(row[8]),
            "tenant_id": row[9],
        }
        for row in rows
    ]


def get_dicom_series(tenant_id: str, study_uid: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT series_instance_uid, study_instance_uid, series_number,
               series_description, modality, num_instances, tenant_id
        FROM dicom_series
        WHERE tenant_id = ? AND study_instance_uid = ?
        ORDER BY series_number ASC
        """,
        (tenant_id, study_uid),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "series_instance_uid": row[0],
            "study_instance_uid": row[1],
            "series_number": row[2] or 0,
            "series_description": row[3] or "",
            "modality": row[4] or "",
            "num_instances": row[5] or 0,
            "tenant_id": row[6],
        }
        for row in rows
    ]


def get_dicom_instances(tenant_id: str, series_uid: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT sop_instance_uid, series_instance_uid, instance_number,
               rows, columns, s3_key, tenant_id, storage_backend
        FROM dicom_instances
        WHERE tenant_id = ? AND series_instance_uid = ?
        ORDER BY instance_number ASC
        """,
        (tenant_id, series_uid),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "sop_instance_uid": row[0],
            "series_instance_uid": row[1],
            "instance_number": row[2] or 0,
            "rows": row[3] or 0,
            "columns": row[4] or 0,
            "s3_key": row[5] or "",
            "tenant_id": row[6],
            "storage_backend": row[7] or "s3",
        }
        for row in rows
    ]


def get_dicom_instance_by_uid(tenant_id: str, sop_uid: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT sop_instance_uid, series_instance_uid, instance_number,
               rows, columns, s3_key, tenant_id, storage_backend
        FROM dicom_instances
        WHERE tenant_id = ? AND sop_instance_uid = ?
        """,
        (tenant_id, sop_uid),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "sop_instance_uid": row[0],
        "series_instance_uid": row[1],
        "instance_number": row[2] or 0,
        "rows": row[3] or 0,
        "columns": row[4] or 0,
        "s3_key": row[5] or "",
        "tenant_id": row[6],
        "storage_backend": row[7] or "s3",
    }


def update_tenant_integration(
    tenant_id: str,
    webhook_url: Optional[str] = None,
    pacs_ae_title: Optional[str] = None,
    pacs_host: Optional[str] = None,
    pacs_port: Optional[int] = None,
    our_ae_title: Optional[str] = None,
    return_path: Optional[str] = None,
    hospital_branding: Optional[str] = None,
) -> None:
    fields = []
    values: List[Any] = []
    for col, val in [
        ("integration_webhook_url", webhook_url),
        ("pacs_ae_title", pacs_ae_title),
        ("pacs_host", pacs_host),
        ("pacs_port", pacs_port),
        ("our_ae_title", our_ae_title),
        ("return_path", return_path),
        ("hospital_branding", hospital_branding),
    ]:
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val)
    if not fields:
        return
    values.append(tenant_id)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE tenants SET {', '.join(fields)} WHERE tenant_id = ?", values)
    conn.commit()
    conn.close()


def get_tenant_integration(tenant_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tenant_id, display_name, integration_webhook_url, pacs_ae_title,
               pacs_host, pacs_port, our_ae_title, return_path, hospital_branding, phi_mode
        FROM tenants WHERE tenant_id = ?
        """,
        (tenant_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "tenant_id": row[0],
        "display_name": row[1] or "",
        "webhook_url": row[2] or "",
        "pacs_ae_title": row[3] or "",
        "pacs_host": row[4] or "",
        "pacs_port": int(row[5] or 0),
        "our_ae_title": row[6] or "INSIDEIMG",
        "return_path": row[7] or "webhook",
        "hospital_branding": row[8] or "",
        "phi_mode": row[9] or "passthrough",
    }


def create_api_key(tenant_id: str, key_hash: str, label: str = "") -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO integration_api_keys (tenant_id, key_hash, label) VALUES (?, ?, ?)",
        (tenant_id, key_hash, label),
    )
    conn.commit()
    key_id = cur.lastrowid
    conn.close()
    return int(key_id)


def lookup_api_key(key_hash: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, tenant_id, label, revoked
        FROM integration_api_keys
        WHERE key_hash = ?
        """,
        (key_hash,),
    )
    row = cur.fetchone()
    if not row or row[3]:
        conn.close()
        return None
    cur.execute(
        "UPDATE integration_api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
        (row[0],),
    )
    conn.commit()
    conn.close()
    return {"id": row[0], "tenant_id": row[1], "label": row[2] or ""}


def revoke_api_key(key_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE integration_api_keys SET revoked = 1 WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()


def insert_integration_report(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO integration_reports (
            tenant_id, source, source_ref, accession_number,
            patient_id_truncated, study_uid, status, inbound_storage_key, language
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("tenant_id", config.DEFAULT_TENANT_ID),
            data.get("source", "http"),
            data.get("source_ref", ""),
            data.get("accession_number", ""),
            data.get("patient_id_truncated", ""),
            data.get("study_uid", ""),
            data.get("status", "received"),
            data.get("inbound_storage_key", ""),
            data.get("language", "English"),
        ),
    )
    conn.commit()
    report_id = cur.lastrowid
    conn.close()
    return int(report_id)


def update_integration_report(
    report_id: int,
    status: Optional[str] = None,
    outbound_pdf_key: Optional[str] = None,
    error: Optional[str] = None,
    mark_processed: bool = False,
) -> None:
    fields = []
    values: List[Any] = []
    if status is not None:
        fields.append("status = ?"); values.append(status)
    if outbound_pdf_key is not None:
        fields.append("outbound_pdf_key = ?"); values.append(outbound_pdf_key)
    if error is not None:
        fields.append("error = ?"); values.append(error)
    if mark_processed:
        fields.append("processed_at = CURRENT_TIMESTAMP")
    if not fields:
        return
    values.append(report_id)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE integration_reports SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_integration_report(report_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, tenant_id, source, source_ref, accession_number,
               patient_id_truncated, study_uid, status, inbound_storage_key,
               outbound_pdf_key, language, error, created_at, processed_at
        FROM integration_reports WHERE id = ?
        """,
        (report_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "tenant_id": row[1], "source": row[2], "source_ref": row[3] or "",
        "accession_number": row[4] or "", "patient_id_truncated": row[5] or "",
        "study_uid": row[6] or "", "status": row[7], "inbound_storage_key": row[8] or "",
        "outbound_pdf_key": row[9] or "", "language": row[10] or "English",
        "error": row[11] or "", "created_at": _format_timestamp(row[12]),
        "processed_at": _format_timestamp(row[13]),
    }
