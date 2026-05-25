"""API key issuance and validation for hospital integrations."""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional, Tuple

from src import db


KEY_PREFIX = "ii_int_"


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def issue_api_key(tenant_id: str, label: str = "") -> Tuple[str, int]:
    """Generate a new API key, persist its hash, and return (raw_key, key_id).

    The raw key is shown ONCE and never stored — caller must capture and
    deliver it to the hospital out-of-band.
    """
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key_id = db.create_api_key(tenant_id, hash_key(raw), label=label)
    return raw, key_id


def resolve_api_key(raw_key: str) -> Optional[dict]:
    if not raw_key:
        return None
    return db.lookup_api_key(hash_key(raw_key))
