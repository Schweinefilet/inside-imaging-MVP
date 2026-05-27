"""Audit log: every PHI access (read/write/return) lands here."""

from __future__ import annotations

from typing import Any, Dict, List

from src import config
from src.db.connection import _format_timestamp, execute, fetch_all


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
    return execute(
        """
        INSERT INTO dicom_audit (
            tenant_id, username, action, resource_type, resource_uid,
            ip_address, user_agent, outcome, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_id or config.DEFAULT_TENANT_ID,
            username or "",
            action, resource_type, resource_uid,
            ip_address, user_agent, outcome, details,
        ),
    )


def get_audit_log(tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    rows = fetch_all(
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
