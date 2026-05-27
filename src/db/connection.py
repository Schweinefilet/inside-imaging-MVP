"""SQLite connection management + initial schema migration."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src import config


DB_PATH = Path("data/patient_data.db")


def get_connection() -> sqlite3.Connection:
    """Return a new database connection (foreign keys enabled, Row factory)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- CRUD shorthands ---------------------------------------------------------
# Every helper in this package follows the same try/finally connection dance.
# These small wrappers eliminate ~200 lines of boilerplate across the package
# and make each query a single statement.

def fetch_one(query: str, params=()) -> Optional["sqlite3.Row"]:
    conn = get_connection()
    try:
        row = conn.execute(query, params).fetchone()
    finally:
        conn.close()
    return row


def fetch_all(query: str, params=()) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return rows


def execute(query: str, params=()) -> int:
    """Run a write query. Returns lastrowid (useful for INSERTs)."""
    conn = get_connection()
    try:
        cur = conn.execute(query, params)
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


def execute_many(stmts: list) -> Optional[int]:
    """Run a sequence of (sql, params) in one transaction. Returns lastrowid of the final statement."""
    conn = get_connection()
    last_id: Optional[int] = None
    try:
        for sql, params in stmts:
            cur = conn.execute(sql, params)
            last_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return int(last_id) if last_id is not None else None


def _format_timestamp(raw: Optional[str]) -> str:
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(str(raw)).strftime("%b %d, %Y %H:%M")
    except Exception:
        return str(raw)


def init_db() -> None:
    """Create / migrate all tables idempotently."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    # --- Analytics: patients (anonymized encounter records) -------------
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
    cur.execute("PRAGMA table_info(patients)")
    cols = [row[1] for row in cur.fetchall()]
    for col, ddl in (
        ("language", "TEXT"),
        ("word_count", "INTEGER DEFAULT 0"),
        ("disease_tags", "TEXT"),
        ("username", "TEXT"),
        ("context", "TEXT"),
    ):
        if col not in cols:
            cur.execute(f"ALTER TABLE patients ADD COLUMN {col} {ddl}")

    # --- Users -----------------------------------------------------------
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
    cur.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cur.fetchall()]
    if "email" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    if "google_id" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")

    # --- Tenants ---------------------------------------------------------
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
    cur.execute("PRAGMA table_info(tenants)")
    tenant_cols = [row[1] for row in cur.fetchall()]
    for col, ddl in (
        ("integration_webhook_url", "TEXT DEFAULT ''"),
        ("pacs_ae_title", "TEXT DEFAULT ''"),
        ("pacs_host", "TEXT DEFAULT ''"),
        ("pacs_port", "INTEGER DEFAULT 0"),
        ("our_ae_title", "TEXT DEFAULT 'INSIDEIMG'"),
        ("return_path", "TEXT DEFAULT 'webhook'"),
        ("hospital_branding", "TEXT DEFAULT ''"),
        ("ip_allowlist", "TEXT DEFAULT ''"),
    ):
        if col not in tenant_cols:
            cur.execute(f"ALTER TABLE tenants ADD COLUMN {col} {ddl}")

    # --- Integration: API keys + reports --------------------------------
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

    # --- Audit log -------------------------------------------------------
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

    # --- DICOM study/series/instance -----------------------------------
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

    # --- Users: tenant_id + lockout columns -----------------------------
    cur.execute("PRAGMA table_info(users)")
    user_cols_v2 = [row[1] for row in cur.fetchall()]
    if "tenant_id" not in user_cols_v2:
        cur.execute(
            f"ALTER TABLE users ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '{config.DEFAULT_TENANT_ID}'"
        )
    if "failed_login_attempts" not in user_cols_v2:
        cur.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
    if "locked_until" not in user_cols_v2:
        cur.execute("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP")
    if "last_login_at" not in user_cols_v2:
        cur.execute("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP")

    # --- Feedback --------------------------------------------------------
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
