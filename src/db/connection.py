"""SQLite connection management + initial schema migration."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src import config


DB_PATH = Path(os.environ.get("DB_PATH", "data/patient_data.db"))

_DB_ENCRYPTION_KEY = (os.environ.get("DB_ENCRYPTION_KEY") or "").strip()


def _get_sqlcipher():
    try:
        import sqlcipher3
        return sqlcipher3
    except ImportError:
        raise RuntimeError(
            "DB_ENCRYPTION_KEY is set but the sqlcipher3 package is not installed.\n"
            "Install it: pip install sqlcipher3\n"
            "  macOS:          brew install sqlcipher\n"
            "  Ubuntu/Debian:  apt install libsqlcipher-dev"
        )


def get_connection() -> sqlite3.Connection:
    """Return a new database connection (foreign keys enabled, Row factory)."""
    import logging as _log
    if _DB_ENCRYPTION_KEY:
        sc = _get_sqlcipher()
        conn = sc.connect(str(DB_PATH))
        try:
            conn.execute(f"PRAGMA key=\"x'{_DB_ENCRYPTION_KEY}'\"")
            conn.execute("SELECT count(*) FROM sqlite_master")
        except Exception as exc:
            conn.close()
            if "not a database" in str(exc).lower():
                raise RuntimeError(
                    f"Database at {DB_PATH} appears unencrypted but DB_ENCRYPTION_KEY is set.\n"
                    "Run: python scripts/encrypt_db.py   to migrate the existing database."
                ) from exc
            raise
        conn.row_factory = sc.Row  # must match the driver — sqlite3.Row rejects sqlcipher3 cursors
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        # File exists but is not a valid SQLite database (e.g. git line-ending
        # corruption or a leftover placeholder).  Delete it and open a fresh one.
        conn.close()
        _log.warning("Corrupt DB file at %s — deleting and starting fresh", DB_PATH)
        try:
            DB_PATH.unlink()
        except OSError:
            pass
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")

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
    except Exception:
        conn.rollback()
        raise
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
    import logging as _logging
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _logging.info("DB_PATH = %s (exists: %s)", DB_PATH.resolve(), DB_PATH.exists())
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
        ("expires_at", "TIMESTAMP"),
        ("raw_text", "TEXT"),
        ("is_sensitive", "INTEGER DEFAULT 0"),
    ):
        if col not in cols:
            cur.execute(f"ALTER TABLE patients ADD COLUMN {col} {ddl}")
    # Backfill expires_at for existing rows using the configured retention window.
    _retention_years = int(os.environ.get("DATA_RETENTION_YEARS", "6"))
    cur.execute(
        f"UPDATE patients SET expires_at = datetime(created_at, '+{_retention_years} years') "
        "WHERE expires_at IS NULL"
    )
    cur.execute("PRAGMA table_info(patients)")
    pat_cols = [row[1] for row in cur.fetchall()]
    if "model_used" not in pat_cols:
        cur.execute("ALTER TABLE patients ADD COLUMN model_used TEXT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patients_created_at ON patients(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patients_language ON patients(language)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patients_sex ON patients(sex)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patients_study ON patients(study)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_patients_username ON patients(username)")

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
            phi_mode TEXT DEFAULT 'pseudonymize',
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
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS audit_no_delete
        BEFORE DELETE ON dicom_audit
        BEGIN
            SELECT RAISE(ABORT, 'Audit records are immutable and cannot be deleted');
        END
        """
    )
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS audit_no_update
        BEFORE UPDATE ON dicom_audit
        BEGIN
            SELECT RAISE(ABORT, 'Audit records are immutable and cannot be modified');
        END
        """
    )

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

    # --- Users: tenant_id + lockout + MFA columns -----------------------
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
    if "totp_secret" not in user_cols_v2:
        cur.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")
    if "totp_enabled" not in user_cols_v2:
        cur.execute("ALTER TABLE users ADD COLUMN totp_enabled INTEGER DEFAULT 0")
    if "specialty" not in user_cols_v2:
        cur.execute("ALTER TABLE users ADD COLUMN specialty TEXT")

    # --- Roles -----------------------------------------------------------
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            assigned_by TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, role)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_roles_username ON user_roles(username)")
    # Seed legacy hardcoded accounts with proper roles so existing deployments
    # continue to work after the RBAC migration.
    for _uname, _role in [("admin", "admin"), ("admin", "radiologist"), ("radiologist", "radiologist")]:
        cur.execute(
            "INSERT OR IGNORE INTO user_roles (username, role, assigned_by) VALUES (?, ?, ?)",
            (_uname, _role, "system_migration"),
        )

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
    cur.execute("PRAGMA table_info(feedback)")
    fb_cols = [row[1] for row in cur.fetchall()]
    for col, ddl in (
        ("embedding", "BLOB"),
        ("modality", "TEXT"),
        ("ai_output", "TEXT"),
        ("report_id", "INTEGER"),
        ("raw_report_text", "TEXT"),
    ):
        if col not in fb_cols:
            cur.execute(f"ALTER TABLE feedback ADD COLUMN {col} {ddl}")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_status_reviewed "
        "ON feedback(status, subject, reviewed_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_user_time_status "
        "ON feedback(username, created_at, status)"
    )

    conn.commit()
    conn.close()
