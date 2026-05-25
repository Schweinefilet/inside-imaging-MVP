"""Centralized runtime configuration for Inside Imaging."""

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


AWS_REGION = _env("AWS_REGION") or _env("AWS_DEFAULT_REGION") or "af-south-1"

STORAGE_BACKEND = _env("STORAGE_BACKEND", "s3").lower()
S3_BUCKET = _env("S3_BUCKET")
LOCAL_STORAGE_PATH = Path(_env("LOCAL_STORAGE_PATH", "data/dicom_storage"))

DEFAULT_TENANT_ID = _env("DEFAULT_TENANT_ID", "default")
DEFAULT_TENANT_NAME = _env("DEFAULT_TENANT_NAME", "Default Tenant")

AUDIT_LOG_ENABLED = _env_bool("AUDIT_LOG_ENABLED", True)

PHI_MODE = _env("PHI_MODE", "passthrough").lower()

# Integration listeners
HL7_LISTENER_HOST = _env("HL7_LISTENER_HOST", "0.0.0.0")
HL7_LISTENER_PORT = int(_env("HL7_LISTENER_PORT", "2575"))
HL7_DEFAULT_TENANT = _env("HL7_DEFAULT_TENANT", DEFAULT_TENANT_ID)
INTEGRATION_BASE_URL = _env("INTEGRATION_BASE_URL", "")
