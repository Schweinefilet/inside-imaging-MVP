"""DICOM Study/Series/Instance tables: tenant-scoped CRUD."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src import config
from src.db.connection import _format_timestamp, execute, execute_many, fetch_all, fetch_one
from src.db.patients import truncate_name


def upsert_dicom_study(data: Dict[str, Any]) -> str:
    # Truncate patient_id before storage — same contract as patient_name_truncated.
    raw_pid = data.get("patient_id") or data.get("patient_id_truncated") or ""
    patient_id_truncated = truncate_name(raw_pid) if raw_pid else ""

    execute(
        """
        INSERT OR IGNORE INTO dicom_studies (
            study_instance_uid, patient_name_truncated, patient_id_truncated, study_date,
            modality, study_description, accession_number, username, tenant_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("study_uid", ""),
            data.get("patient_name_truncated", ""),
            patient_id_truncated,
            data.get("study_date", ""),
            data.get("modality", ""),
            data.get("study_description", ""),
            data.get("accession_number", ""),
            data.get("username", ""),
            data.get("tenant_id", config.DEFAULT_TENANT_ID),
        ),
    )
    return str(data.get("study_uid", ""))


def upsert_dicom_series(data: Dict[str, Any]) -> str:
    series_uid = data.get("series_uid", "")
    execute_many([
        (
            """
            INSERT OR IGNORE INTO dicom_series (
                series_instance_uid, study_instance_uid, series_number,
                series_description, modality, num_instances, tenant_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                series_uid,
                data.get("study_uid", ""),
                data.get("series_number", 0) or 0,
                data.get("series_description", ""),
                data.get("modality", ""),
                0,
                data.get("tenant_id", config.DEFAULT_TENANT_ID),
            ),
        ),
        (
            "UPDATE dicom_series SET num_instances = num_instances + 1 WHERE series_instance_uid = ?",
            (series_uid,),
        ),
    ])
    return str(series_uid)


def insert_dicom_instance(data: Dict[str, Any]) -> int:
    return execute(
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


def _study_row(row) -> Dict[str, Any]:
    return {
        "study_instance_uid": row[0],
        "patient_name_truncated": row[1] or "",
        "patient_id_truncated": row[2] or "",
        "study_date": row[3] or "",
        "modality": row[4] or "",
        "study_description": row[5] or "",
        "accession_number": row[6] or "",
        "username": row[7] or "",
        "created_at": _format_timestamp(row[8]),
        "tenant_id": row[9],
    }


def get_dicom_studies(tenant_id: str, username: Optional[str] = None) -> List[Dict[str, Any]]:
    base = ("SELECT study_instance_uid, patient_name_truncated, patient_id_truncated, study_date,"
            " modality, study_description, accession_number, username, created_at, tenant_id"
            " FROM dicom_studies WHERE tenant_id = ?")
    if username:
        rows = fetch_all(base + " AND username = ? ORDER BY datetime(created_at) DESC",
                         (tenant_id, username))
    else:
        rows = fetch_all(base + " ORDER BY datetime(created_at) DESC", (tenant_id,))
    return [_study_row(r) for r in rows]


def get_dicom_series(tenant_id: str, study_uid: str) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT series_instance_uid, study_instance_uid, series_number,
               series_description, modality, num_instances, tenant_id
        FROM dicom_series
        WHERE tenant_id = ? AND study_instance_uid = ?
        ORDER BY series_number ASC
        """,
        (tenant_id, study_uid),
    )
    return [
        {
            "series_instance_uid": r[0],
            "study_instance_uid": r[1],
            "series_number": r[2] or 0,
            "series_description": r[3] or "",
            "modality": r[4] or "",
            "num_instances": r[5] or 0,
            "tenant_id": r[6],
        }
        for r in rows
    ]


def _instance_row(row) -> Dict[str, Any]:
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


def get_dicom_instances(tenant_id: str, series_uid: str) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT sop_instance_uid, series_instance_uid, instance_number,
               rows, columns, s3_key, tenant_id, storage_backend
        FROM dicom_instances
        WHERE tenant_id = ? AND series_instance_uid = ?
        ORDER BY instance_number ASC
        """,
        (tenant_id, series_uid),
    )
    return [_instance_row(r) for r in rows]


def get_dicom_instance_by_uid(tenant_id: str, sop_uid: str) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        """
        SELECT sop_instance_uid, series_instance_uid, instance_number,
               rows, columns, s3_key, tenant_id, storage_backend
        FROM dicom_instances
        WHERE tenant_id = ? AND sop_instance_uid = ?
        """,
        (tenant_id, sop_uid),
    )
    return _instance_row(row) if row else None
