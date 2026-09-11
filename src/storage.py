"""Pluggable object storage backends for DICOM payloads."""

from __future__ import annotations

import os
import re
import stat
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config

from src import config


class Storage(ABC):
    backend_name: str = "abstract"

    @abstractmethod
    def put(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
        ...

    @abstractmethod
    def get(self, key: str) -> bytes:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...


class S3Storage(Storage):
    backend_name = "s3"

    def __init__(self, bucket: str, region: str, endpoint_url: Optional[str] = None,
                 kms_key_id: Optional[str] = None):
        if not bucket:
            raise RuntimeError("S3Storage requires a bucket name (set S3_BUCKET).")
        self.bucket = bucket
        self.kms_key_id = kms_key_id
        client_kwargs = {
            "region_name": region,
            "config": Config(retries={"max_attempts": 3, "mode": "standard"}),
        }
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        self._client = boto3.client("s3", **client_kwargs)

    def put(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
        kwargs = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": body,
            "ContentType": content_type,
        }
        # Prefer SSE-KMS when a key is configured; fall back to SSE-S3 otherwise.
        # Either way, server-side encryption is explicit (not relying on bucket default).
        if self.kms_key_id:
            kwargs["ServerSideEncryption"] = "aws:kms"
            kwargs["SSEKMSKeyId"] = self.kms_key_id
        else:
            kwargs["ServerSideEncryption"] = "AES256"
        self._client.put_object(**kwargs)
        return key

    def get(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


class LocalFileStorage(Storage):
    backend_name = "local"

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        full = (self.root / key).resolve()
        if not str(full).startswith(str(self.root.resolve())):
            raise ValueError(f"Storage key escapes root: {key!r}")
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    def put(self, key: str, body: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        # Explicit 0600 rather than relying on the process umask: this
        # directory holds unencrypted PHI (DICOM files) when
        # STORAGE_BACKEND=local, so it must not default to group/world
        # readable on a shared host.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            fh = os.fdopen(fd, "wb")
        except Exception:
            os.close(fd)
            raise
        with fh:
            fh.write(body)
        return key

    def get(self, key: str) -> bytes:
        with open(self._path(key), "rb") as fh:
            return fh.read()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


_storage_singleton: Optional[Storage] = None


def get_storage() -> Storage:
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton

    backend = config.STORAGE_BACKEND
    if backend == "local":
        _storage_singleton = LocalFileStorage(config.LOCAL_STORAGE_PATH)
    elif backend in ("s3", "minio"):
        endpoint = os.getenv("S3_ENDPOINT_URL") or None
        kms_key = os.getenv("S3_KMS_KEY_ID") or None  # ARN, key id, or alias/...
        _storage_singleton = S3Storage(
            config.S3_BUCKET, config.AWS_REGION,
            endpoint_url=endpoint, kms_key_id=kms_key,
        )
    else:
        raise RuntimeError(f"Unknown STORAGE_BACKEND: {backend!r}")

    return _storage_singleton


def reset_storage_singleton() -> None:
    global _storage_singleton
    _storage_singleton = None


_SAFE_KEY_SEGMENT_RX = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_key_segment(name: str, value: str) -> str:
    """Validate a value that becomes one path segment of a storage key.

    study_uid/series_uid/sop_uid come straight from an uploaded DICOM file's
    tags with no format check upstream — a crafted UID containing "/" or ".."
    wouldn't escape the storage root (LocalFileStorage._path already blocks
    that), but could still land the file under a DIFFERENT tenant's own
    subtree within that same root (tenant path confusion). Real DICOM UIDs
    are dot-separated digits; reject anything else outright.
    """
    if not value or not _SAFE_KEY_SEGMENT_RX.match(value):
        raise ValueError(f"Invalid {name} for storage key: {value!r}")
    return value


def dicom_key(tenant_id: str, study_uid: str, series_uid: str, sop_uid: str) -> str:
    tenant_id = _safe_key_segment("tenant_id", tenant_id)
    study_uid = _safe_key_segment("study_uid", study_uid)
    series_uid = _safe_key_segment("series_uid", series_uid)
    sop_uid = _safe_key_segment("sop_uid", sop_uid)
    return f"tenants/{tenant_id}/dicom/{study_uid}/{series_uid}/{sop_uid}.dcm"
