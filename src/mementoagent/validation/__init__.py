"""TOML shape loading and evidence grounding."""

from .invariants import normalize_whitespace, validate_record
from .shape import LoadedRecord, RecordLoadError, load_record_file

__all__ = [
    "LoadedRecord",
    "RecordLoadError",
    "load_record_file",
    "normalize_whitespace",
    "validate_record",
]
