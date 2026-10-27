"""Read-only record validation and verification seals."""

from .invariants import CheckResult, Issue, normalize_whitespace, validate_record
from .seal import canonical_critical_fields, compute_seal, verify_seal
from .shape import LoadedRecord, RecordLoadError, load_record_file

__all__ = [
    "CheckResult",
    "Issue",
    "LoadedRecord",
    "RecordLoadError",
    "canonical_critical_fields",
    "compute_seal",
    "load_record_file",
    "normalize_whitespace",
    "validate_record",
    "verify_seal",
]
