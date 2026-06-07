"""Integration: API keys for hospital systems and report-pipeline state."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src import config
from src.db.connection import _format_timestamp, execute, execute_many, fetch_one


# --- API keys ---------------------------------------------------------------

def create_api_key(tenant_id: str, key_hash: str, label: str = "") -> int:
    return execute(
        "INSERT INTO integration_api_keys (tenant_id, key_hash, label) VALUES (?, ?, ?)",
        (tenant_id, key_hash, label),
    )


def lookup_api_key(key_hash: str) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        "SELECT id, tenant_id, label, revoked FROM integration_api_keys WHERE key_hash = ?",
        (key_hash,),
    )
    if not row or row[3]:
        return None
    # touch last_used_at; failure here is non-fatal
    execute(
        "UPDATE integration_api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
        (row[0],),
    )
    return {"id": row[0], "tenant_id": row[1], "label": row[2] or ""}


def revoke_api_key(key_id: int) -> None:
    execute("UPDATE integration_api_keys SET revoked = 1 WHERE id = ?", (key_id,))


# --- Integration reports ----------------------------------------------------

def insert_integration_report(data: Dict[str, Any]) -> int:
    return execute(
        """
        INSERT INTO integration_reports (
            tenant_id, source, source_ref, accession_number,
            patient_id_truncated, study_uid, status, inbound_storage_key, language, flagged
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            1 if data.get("flagged") else 0,
        ),
    )


def update_integration_report(
    report_id: int,
    status: Optional[str] = None,
    outbound_pdf_key: Optional[str] = None,
    inbound_storage_key: Optional[str] = None,
    flagged: Optional[bool] = None,
    error: Optional[str] = None,
    mark_processed: bool = False,
) -> None:
    sets: List[str] = []
    values: List[Any] = []
    if status is not None:
        sets.append("status = ?"); values.append(status)
    if outbound_pdf_key is not None:
        sets.append("outbound_pdf_key = ?"); values.append(outbound_pdf_key)
    if inbound_storage_key is not None:
        sets.append("inbound_storage_key = ?"); values.append(inbound_storage_key)
    if flagged is not None:
        sets.append("flagged = ?"); values.append(1 if flagged else 0)
    if error is not None:
        sets.append("error = ?"); values.append(error)
    if mark_processed:
        sets.append("processed_at = CURRENT_TIMESTAMP")
    if not sets:
        return
    values.append(report_id)
    execute(f"UPDATE integration_reports SET {', '.join(sets)} WHERE id = ?", values)


def get_integration_report(report_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        """
        SELECT id, tenant_id, source, source_ref, accession_number,
               patient_id_truncated, study_uid, status, inbound_storage_key,
               outbound_pdf_key, language, flagged, error, created_at, processed_at
        FROM integration_reports WHERE id = ?
        """,
        (report_id,),
    )
    if not row:
        return None
    return {
        "id": row[0], "tenant_id": row[1], "source": row[2], "source_ref": row[3] or "",
        "accession_number": row[4] or "", "patient_id_truncated": row[5] or "",
        "study_uid": row[6] or "", "status": row[7], "inbound_storage_key": row[8] or "",
        "outbound_pdf_key": row[9] or "", "language": row[10] or "English",
        "flagged": bool(row[11]),
        "error": row[12] or "", "created_at": _format_timestamp(row[13]),
        "processed_at": _format_timestamp(row[14]),
    }


def revoke_api_key_by_label(tenant_id: str, label: str) -> int:
    """Revoke all non-revoked keys matching tenant_id + label. Returns count revoked."""
    execute(
        "UPDATE integration_api_keys SET revoked = 1"
        " WHERE tenant_id = ? AND label = ? AND revoked = 0",
        (tenant_id, label),
    )
    row = fetch_one(
        "SELECT COUNT(*) FROM integration_api_keys WHERE tenant_id = ? AND label = ? AND revoked = 1",
        (tenant_id, label),
    )
    return int(row[0]) if row else 0


def revoke_api_key_by_hash(key_hash: str) -> bool:
    """Revoke a key by its SHA-256 hash. Returns True if found and revoked."""
    row = fetch_one(
        "SELECT id, revoked FROM integration_api_keys WHERE key_hash = ?", (key_hash,)
    )
    if not row:
        return False
    execute("UPDATE integration_api_keys SET revoked = 1 WHERE id = ?", (row[0],))
    return True
