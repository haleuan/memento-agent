"""Deterministic SHA-256 seals over a record's critical fields."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel


def canonical_critical_fields(record: BaseModel | Mapping[str, Any]) -> bytes:
    """Serialize the record type's declared critical fields as canonical JSON.

    The data schema declares its critical field names. ``occurred`` is also
    included, while evidence remains independently validated and does not affect
    verification. Model defaults and nulls remain present.

    Args:
        record: A validated model or mapping with the critical record fields.

    Returns:
        Compact, sorted-key JSON encoded as UTF-8 bytes.

    Raises:
        KeyError: If a required critical field is missing from the record.
        ValueError: If the fields cannot be serialized as strict JSON.
    """
    payload = (
        record.model_dump(mode="json", by_alias=True)
        if isinstance(record, BaseModel)
        else dict(record)
    )
    if isinstance(record, BaseModel):
        field_names = record.data.CRITICAL_FIELDS
    else:
        field_names = ("kind", "title", "issuer", "level_raw")
    critical = {
        "data": {key: payload["data"][key] for key in field_names},
        "occurred": payload.get("occurred"),
    }
    return json.dumps(
        critical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_seal(record: BaseModel | Mapping[str, Any]) -> str:
    """Compute a SHA-256 seal for a record's critical fields.

    Args:
        record: A validated model or mapping with the critical record fields.

    Returns:
        A seal prefixed with ``sha256:``.
    """
    return "sha256:" + hashlib.sha256(canonical_critical_fields(record)).hexdigest()


def verify_seal(record: BaseModel | Mapping[str, Any]) -> bool:
    """Check whether a human verification seal matches the record.

    Args:
        record: A validated model or mapping with verification metadata.

    Returns:
        ``True`` when a human seal exists and matches the critical fields.
    """
    payload = (
        record.model_dump(mode="json", by_alias=True)
        if isinstance(record, BaseModel)
        else dict(record)
    )
    verification = payload.get("verification")
    return bool(
        verification
        and verification.get("by") == "human"
        and verification.get("sealed") == compute_seal(record)
    )
