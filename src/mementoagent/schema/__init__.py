"""Public Pydantic schemas for the Memento data layer."""

from .achievement import AchievementData
from .envelope import (
    Evidence,
    HashId,
    Occurred,
    RecordData,
    RecordEnvelope,
    RecordId,
    SchemaVersion,
    Verification,
)
from .parse import ParseMeta, ParsedBlock
from .source import SourceMetadata

ENVELOPE_SCHEMA_VERSION = "envelope/1"
ACHIEVEMENT_SCHEMA_VERSION = "achievement/1"

__all__ = [
    "ACHIEVEMENT_SCHEMA_VERSION",
    "ENVELOPE_SCHEMA_VERSION",
    "AchievementData",
    "Evidence",
    "HashId",
    "Occurred",
    "ParseMeta",
    "ParsedBlock",
    "RecordData",
    "RecordEnvelope",
    "RecordId",
    "SchemaVersion",
    "SourceMetadata",
    "Verification",
]
