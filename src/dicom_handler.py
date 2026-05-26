"""DICOM file ingestion and image extraction utilities."""

from __future__ import annotations

import hashlib
import io
from typing import Any, Dict

import numpy as np
import pydicom
from PIL import Image

from src import db
from src.storage import Storage, dicom_key


# DICOM tags that carry direct PHI per the DICOM standard's Basic Profile.
# Stripped before S3 put when tenant phi_mode != 'passthrough'.
_PHI_TAGS_TO_REMOVE = [
    "PatientName", "PatientID", "PatientBirthDate", "PatientBirthTime", "PatientAddress",
    "PatientTelephoneNumbers", "PatientMotherBirthName", "OtherPatientIDs", "OtherPatientNames",
    "PatientWeight", "PatientSize", "PatientComments", "MilitaryRank", "EthnicGroup",
    "ReferringPhysicianName", "ReferringPhysicianAddress", "ReferringPhysicianTelephoneNumbers",
    "PerformingPhysicianName", "OperatorsName", "RequestingPhysician", "PhysiciansOfRecord",
    "InstitutionAddress", "StationName",
    "StudyComments", "AdmissionID", "IssuerOfPatientID", "AccessionNumber",
]


def _pseudonym(value: str, salt: str) -> str:
    if not value:
        return ""
    return "p_" + hashlib.sha256((salt + ":" + value).encode("utf-8")).hexdigest()[:12]


def sanitize_dicom_bytes(dcm_bytes: bytes, mode: str, tenant_salt: str = "") -> bytes:
    """Return new DICOM bytes with PHI tags removed/replaced according to mode.
    mode: 'passthrough' (return as-is), 'pseudonymize', or 'full_deidentify'."""
    if mode == "passthrough" or not dcm_bytes:
        return dcm_bytes

    ds = pydicom.dcmread(io.BytesIO(dcm_bytes), force=True)

    if mode == "pseudonymize":
        # Replace PatientName/PatientID with stable hashed tokens; clear the rest.
        if hasattr(ds, "PatientName"):
            ds.PatientName = _pseudonym(str(ds.PatientName), tenant_salt)
        if hasattr(ds, "PatientID"):
            ds.PatientID = _pseudonym(str(ds.PatientID), tenant_salt)
        for tag in _PHI_TAGS_TO_REMOVE:
            if tag in ("PatientName", "PatientID"):
                continue
            if hasattr(ds, tag):
                try:
                    delattr(ds, tag)
                except Exception:
                    pass
    else:  # full_deidentify
        for tag in _PHI_TAGS_TO_REMOVE:
            if hasattr(ds, tag):
                try:
                    delattr(ds, tag)
                except Exception:
                    pass
        if hasattr(ds, "PatientName"):
            ds.PatientName = "ANON^PATIENT"
        if hasattr(ds, "PatientID"):
            ds.PatientID = "ANON"

    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds, write_like_original=True)
    return buf.getvalue()


def _str_tag(ds: "pydicom.Dataset", tag: str, default: str = "") -> str:
    value = getattr(ds, tag, None)
    if value is None or value == "":
        return default
    return str(value)


def _int_tag(ds: "pydicom.Dataset", tag: str, default: int = 0) -> int:
    value = getattr(ds, tag, None)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_dicom_metadata(dcm_bytes: bytes) -> Dict[str, Any]:
    ds = pydicom.dcmread(io.BytesIO(dcm_bytes), force=True, stop_before_pixels=True)

    return {
        "study_uid": _str_tag(ds, "StudyInstanceUID"),
        "series_uid": _str_tag(ds, "SeriesInstanceUID"),
        "sop_uid": _str_tag(ds, "SOPInstanceUID"),
        "patient_name_truncated": db.truncate_name(_str_tag(ds, "PatientName")),
        "patient_id": _str_tag(ds, "PatientID"),
        "study_date": _str_tag(ds, "StudyDate"),
        "modality": _str_tag(ds, "Modality"),
        "study_description": _str_tag(ds, "StudyDescription"),
        "accession_number": _str_tag(ds, "AccessionNumber"),
        "series_number": _int_tag(ds, "SeriesNumber"),
        "series_description": _str_tag(ds, "SeriesDescription"),
        "instance_number": _int_tag(ds, "InstanceNumber"),
        "rows": _int_tag(ds, "Rows"),
        "columns": _int_tag(ds, "Columns"),
    }


def _apply_window(arr: np.ndarray, center: float, width: float) -> np.ndarray:
    low = center - width / 2.0
    high = center + width / 2.0
    clipped = np.clip(arr, low, high)
    return (clipped - low) / max(high - low, 1.0)


def extract_frame_as_png(dcm_bytes: bytes) -> bytes:
    ds = pydicom.dcmread(io.BytesIO(dcm_bytes), force=True)

    try:
        arr = ds.pixel_array
    except Exception as exc:
        raise ValueError("No pixel data") from exc

    if arr is None or arr.size == 0:
        raise ValueError("No pixel data")

    if arr.ndim > 2 and arr.shape[0] > 1 and arr.shape[-1] not in (3, 4):
        arr = arr[0]

    is_color = arr.ndim == 3 and arr.shape[-1] in (3, 4)

    if is_color:
        norm = arr.astype(np.float32)
        norm = norm - norm.min()
        peak = norm.max()
        if peak > 0:
            norm = norm / peak
    else:
        arr = arr.astype(np.float32)
        center = getattr(ds, "WindowCenter", None)
        width = getattr(ds, "WindowWidth", None)
        if isinstance(center, pydicom.multival.MultiValue):
            center = float(center[0])
        if isinstance(width, pydicom.multival.MultiValue):
            width = float(width[0])
        if center is not None and width is not None and float(width) > 0:
            norm = _apply_window(arr, float(center), float(width))
        else:
            lo, hi = np.percentile(arr, [2, 98])
            if hi <= lo:
                hi = lo + 1.0
            norm = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)

    pixels = (norm * 255.0).astype(np.uint8)

    if is_color:
        mode = "RGBA" if pixels.shape[-1] == 4 else "RGB"
        image = Image.fromarray(pixels, mode=mode)
    else:
        image = Image.fromarray(pixels, mode="L")

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def store_dicom(
    storage: Storage,
    dcm_bytes: bytes,
    tenant_id: str,
    study_uid: str,
    series_uid: str,
    sop_uid: str,
) -> str:
    key = dicom_key(tenant_id, study_uid, series_uid, sop_uid)
    storage.put(key, dcm_bytes, content_type="application/dicom")
    return key
