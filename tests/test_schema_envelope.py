"""Tests for record envelope schemas and their shared constrained types."""

import pytest
from pydantic import TypeAdapter, ValidationError

from mementoagent.schema import (
    AchievementItem,
    Evidence,
    HashId,
    RecordEnvelope,
    RecordId,
    SchemaVersion,
    Verification,
)
from mementoagent.schema.envelope import TimeRange, Timestamp
from mementoagent.schema.types import PartialDate

VALID_HASH = "sha256:" + "a" * 64
VALID_RECORD_ID = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"


def test_hash_id_accepts_valid_sha256_identifier() -> None:
    """Accept a lowercase 64-digit SHA-256 source identifier."""
    assert TypeAdapter(HashId).validate_python(VALID_HASH) == VALID_HASH


@pytest.mark.parametrize(
    "value",
    [
        "sha256:",
        "sha256:" + "a" * 63,
        "sha256:" + "a" * 65,
        "sha256:" + "A" * 64,
        "md5:" + "a" * 64,
    ],
)
def test_hash_id_rejects_malformed_identifier(value: str) -> None:
    """Reject source identifiers that do not match the SHA-256 format."""
    with pytest.raises(ValidationError):
        TypeAdapter(HashId).validate_python(value)


def test_record_id_accepts_type_prefixed_ulid() -> None:
    """Accept a lowercase record type followed by a valid ULID."""
    assert TypeAdapter(RecordId).validate_python(VALID_RECORD_ID) == VALID_RECORD_ID


@pytest.mark.parametrize(
    "value",
    [
        "ach_81JBX7Q3M8K2N5R9V4W6Y0ZDEF",
        "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEI",
        "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDE",
    ],
)
def test_record_id_rejects_malformed_identifier(value: str) -> None:
    """Reject invalid record type or ULID components."""
    with pytest.raises(ValidationError):
        TypeAdapter(RecordId).validate_python(value)


def test_schema_version_accepts_type_and_positive_version() -> None:
    """Accept a lowercase schema type and positive integer version."""
    assert (
        TypeAdapter(SchemaVersion).validate_python("achievement/1") == "achievement/1"
    )


@pytest.mark.parametrize(
    "value", ["achievement", "achievement/0", "Achievement/1", "achievement/v1"]
)
def test_schema_version_rejects_malformed_value(value: str) -> None:
    """Reject schema versions outside the type/version format."""
    with pytest.raises(ValidationError):
        TypeAdapter(SchemaVersion).validate_python(value)


def test_timestamp_accepts_timezone_aware_iso_value() -> None:
    """Accept an ISO 8601 timestamp that includes a timezone."""
    value = "2025-01-12T09:30:00+08:00"

    assert TypeAdapter(Timestamp).validate_python(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "2025-01-12T09:30:00",
        "2025-01-12",
        "not-a-timestamp",
    ],
)
def test_timestamp_rejects_naive_or_non_iso_value(value: str) -> None:
    """Reject timestamps without both ISO datetime syntax and timezone data."""
    with pytest.raises(ValidationError):
        TypeAdapter(Timestamp).validate_python(value)


def test_time_range_accepts_partial_dates() -> None:
    """Store partial start and end dates without changing their precision."""
    start = PartialDate(year=2024, month=1, precision="month")
    end = PartialDate(year=2024, month=3, day=15, precision="day")

    result = TimeRange(start=start, end=end)

    assert result.start == start
    assert result.end == end


def test_evidence_accepts_quote_and_supporting_fields() -> None:
    """Store a source hash, page, quote, and supported field paths."""
    result = Evidence(
        source=VALID_HASH,
        page=2,
        quote="First Prize",
        supports=["data.title", "data.level_raw"],
    )

    assert result.source == VALID_HASH
    assert result.page == 2
    assert result.quote == "First Prize"
    assert result.supports == ["data.title", "data.level_raw"]


@pytest.mark.parametrize("quote", ["", "   ", "\t\n"])
def test_evidence_rejects_whitespace_only_quote(quote: str) -> None:
    """Reject evidence quotes that contain no non-whitespace text."""
    with pytest.raises(ValidationError):
        Evidence(source=VALID_HASH, quote=quote)


def test_verification_accepts_verifier_and_timestamp() -> None:
    """Store the verifier identifier and timezone-aware verification time."""
    result = Verification(by="reviewer", at="2025-01-12T09:30:00+08:00")

    assert result.by == "reviewer"
    assert result.at == "2025-01-12T09:30:00+08:00"


def test_record_envelope_accepts_complete_achievement_record() -> None:
    """Instantiate an achievement envelope with all supported metadata."""
    data = AchievementItem(
        kind="award",
        title="National Mathematical Modeling Contest",
        organization="Competition Committee",
    )
    record = RecordEnvelope[AchievementItem](
        id=VALID_RECORD_ID,
        schema="achievement/1",
        provenance="document",
        created_at="2025-01-12T09:30:00+08:00",
        occurred=TimeRange(
            start=PartialDate(year=2024, month=10, day=15, precision="day")
        ),
        data=data,
        evidence=[Evidence(source=VALID_HASH, quote="First Prize")],
        verification=Verification(by="reviewer", at="2025-01-13T09:30:00+08:00"),
    )

    assert record.schema_version == "achievement/1"
    assert record.data == data
    assert record.evidence[0].source == VALID_HASH
    assert record.verification is not None
    assert record.model_dump(by_alias=True)["schema"] == "achievement/1"


def test_record_envelope_rejects_removed_body_field() -> None:
    """Reject a free-form body outside the structured record schema."""
    data = AchievementItem(
        kind="award",
        title="First Prize",
        organization="Competition Committee",
    )

    with pytest.raises(ValidationError):
        RecordEnvelope[AchievementItem](
            id=VALID_RECORD_ID,
            schema="achievement/1",
            provenance="user",
            created_at="2025-01-12T09:30:00+08:00",
            data=data,
            body="Legacy Markdown body",
        )
