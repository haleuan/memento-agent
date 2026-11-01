"""Public Pydantic schemas for the Memento data layer."""

from .achievement import AchievementItem, AchievementReference
from .envelope import (
    Evidence,
    HashId,
    RecordEnvelope,
    RecordId,
    SchemaVersion,
    Verification,
)
from .ids import generate_record_id
from .parsing import ParseSnapshot, ParseSnapshotMetadata
from .types import PartialDate

ENVELOPE_SCHEMA_VERSION = "envelope/1"
ACHIEVEMENT_SCHEMA_VERSION = "achievement/1"

__all__ = [
    "ACHIEVEMENT_SCHEMA_VERSION",
    "ENVELOPE_SCHEMA_VERSION",
    "AchievementItem",
    "AchievementReference",
    "Evidence",
    "generate_record_id",
    "HashId",
    "ParseSnapshot",
    "ParseSnapshotMetadata",
    "RecordEnvelope",
    "RecordId",
    "SchemaVersion",
    "Verification",
    "PartialDate",
]
