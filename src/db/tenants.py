"""Tenant management: per-hospital config, integration settings, PHI mode."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src import config
from src.db.connection import _format_timestamp, execute, fetch_one


def get_user_tenant(username: str) -> str:
    if not username:
        return config.DEFAULT_TENANT_ID
    row = fetch_one("SELECT tenant_id FROM users WHERE username = ?", (username,))
    return str(row[0]) if row and row[0] else config.DEFAULT_TENANT_ID


def get_tenant(tenant_id: str) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        "SELECT tenant_id, display_name, region, phi_mode, created_at"
        " FROM tenants WHERE tenant_id = ?",
        (tenant_id,),
    )
    if not row:
        return None
    return {
        "tenant_id": row[0],
        "display_name": row[1] or "",
        "region": row[2] or "",
        "phi_mode": row[3] or "passthrough",
        "created_at": _format_timestamp(row[4]),
    }


def create_tenant(tenant_id: str, display_name: str = "",
                  region: str = "", phi_mode: str = "passthrough") -> None:
    execute(
        "INSERT OR IGNORE INTO tenants (tenant_id, display_name, region, phi_mode)"
        " VALUES (?, ?, ?, ?)",
        (tenant_id, display_name, region, phi_mode),
    )


_TENANT_INTEGRATION_FIELDS = (
    ("integration_webhook_url", "webhook_url"),
    ("pacs_ae_title", "pacs_ae_title"),
    ("pacs_host", "pacs_host"),
    ("pacs_port", "pacs_port"),
    ("our_ae_title", "our_ae_title"),
    ("return_path", "return_path"),
    ("hospital_branding", "hospital_branding"),
    ("ip_allowlist", "ip_allowlist"),
)


def update_tenant_integration(tenant_id: str, **kwargs) -> None:
    """Update any subset of tenant integration fields by keyword.
    Accepted keys: webhook_url, pacs_ae_title, pacs_host, pacs_port,
    our_ae_title, return_path, hospital_branding, ip_allowlist."""
    sets: List[str] = []
    values: List[Any] = []
    for col, kw in _TENANT_INTEGRATION_FIELDS:
        if kwargs.get(kw) is not None:
            sets.append(f"{col} = ?")
            values.append(kwargs[kw])
    if not sets:
        return
    values.append(tenant_id)
    execute(f"UPDATE tenants SET {', '.join(sets)} WHERE tenant_id = ?", values)


def get_tenant_integration(tenant_id: str) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        """
        SELECT tenant_id, display_name, integration_webhook_url, pacs_ae_title,
               pacs_host, pacs_port, our_ae_title, return_path, hospital_branding,
               phi_mode, ip_allowlist
        FROM tenants WHERE tenant_id = ?
        """,
        (tenant_id,),
    )
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
        "ip_allowlist": row[10] or "",
    }
