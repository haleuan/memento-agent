"""Public Pydantic schemas for the Memento data layer."""

from .achievement import AchievementItem
from .envelope import (
    Evidence,
    HashId,
    RecordEnvelope,
    RecordId,
    SchemaVersion,
    Verification,
)
from .parsing import ParseSnapshot, ParseSnapshotMetadata
from .types import PartialDate

ENVELOPE_SCHEMA_VERSION = "envelope/1"
ACHIEVEMENT_SCHEMA_VERSION = "achievement/1"

__all__ = [
    "ACHIEVEMENT_SCHEMA_VERSION",
    "ENVELOPE_SCHEMA_VERSION",
    "AchievementItem",
    "Evidence",
    "HashId",
    "ParseSnapshot",
    "ParseSnapshotMetadata",
    "RecordEnvelope",
    "RecordId",
    "SchemaVersion",
    "Verification",
    "PartialDate",
]
