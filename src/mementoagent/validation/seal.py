"""Deterministic SHA-256 seals over a record's critical fields."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel


def canonical_critical_fields(record: BaseModel | Mapping[str, Any]) -> bytes:
    """Serialize ``data``, ``occurred``, and ``evidence`` to canonical UTF-8 JSON.

    Model defaults and nulls remain present; arrays retain their original order.
    Whitespace and Unicode in factual strings are never normalized for sealing.

    Args:
        record: A validated model or mapping with the critical record fields.

    Returns:
        Compact, sorted-key JSON encoded as UTF-8 bytes.

    Raises:
        KeyError: If a critical field is missing from the mapping.
        ValueError: If the fields cannot be serialized as strict JSON.
    """
    payload = (
        record.model_dump(mode="json", by_alias=True)
        if isinstance(record, BaseModel)
        else dict(record)
    )
    critical = {key: payload[key] for key in ("data", "occurred", "evidence")}
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
