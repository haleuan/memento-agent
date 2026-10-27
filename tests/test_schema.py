"""Adversarial shape checks for the public record and snapshot schemas."""

from copy import deepcopy
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from mementoagent.schema import (
    AchievementData,
    Evidence,
    ParseMeta,
    ParsedBlock,
    RecordEnvelope,
    SourceMetadata,
    Verification,
)


HASH = "sha256:" + "a" * 64
TIMESTAMP = "2025-01-12T09:30:00+08:00"


def achievement_record() -> dict:
    """Build a valid achievement record payload."""
    return {
        "id": "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF",
        "schema": "achievement/1",
        "provenance": "document",
        "created_at": TIMESTAMP,
        "occurred": {"start": "2024-10", "end": "2024-10"},
        "data": {
            "kind": "award",
            "title": "XX 大学生程序设计竞赛",
            "issuer": "XX 竞赛组委会",
            "level_raw": "省赛二等奖",
        },
        "evidence": [{
            "source": HASH,
            "parse": "p_20250112_093045",
            "block": "p0-b07",
            "supports": ["data.title", "data.issuer", "data.level_raw", "occurred"],
            "quote": "荣获省赛二等奖",
        }],
    }


def test_typed_envelope_preserves_raw_text_and_partial_dates():
    """Preserve raw achievement text and partial dates in typed records."""
    record = RecordEnvelope[AchievementData].model_validate(achievement_record())

    assert isinstance(record.data, AchievementData)
    assert record.data.level_raw == "省赛二等奖"
    assert record.occurred.start == "2024-10"
    assert record.verification is None
    assert record.model_dump(mode="json", by_alias=True)["schema"] == "achievement/1"


@pytest.mark.parametrize("unexpected_field", ["status", "review_flags", "unknown"])
def test_envelope_rejects_derived_and_unknown_fields(unexpected_field):
    """Reject derived status and unexpected envelope fields."""
    data = achievement_record()
    data[unexpected_field] = "verified"

    with pytest.raises(ValidationError):
        RecordEnvelope[AchievementData].model_validate(data)


@pytest.mark.parametrize("field,value", [
    ("id", "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEI"),
    ("id", "ach_81JBX7Q3M8K2N5R9V4W6Y0ZDEF"),
    ("id", "ach_1"),
    ("schema", "achievement/0"),
    ("schema", "achievement"),
    ("created_at", "2025-01-12T09:30:00"),
    ("created_at", "2025-01-12"),
    ("created_at", datetime(2025, 1, 12, tzinfo=timezone.utc)),
])
def test_envelope_rejects_invalid_identifiers_and_timestamps(field, value):
    """Reject malformed record IDs, schema versions, and timestamps."""
    data = achievement_record()
    data[field] = value

    with pytest.raises(ValidationError):
        RecordEnvelope[AchievementData].model_validate(data)


def test_occurred_rejects_date_objects():
    """Reject date objects in occurred fields to retain strict strings."""
    data = achievement_record()
    data["occurred"]["start"] = date(2024, 10, 1)

    with pytest.raises(ValidationError):
        RecordEnvelope[AchievementData].model_validate(data)


@pytest.mark.parametrize("field,value", [
    ("source", "sha256:" + "A" * 64),
    ("source", "a" * 64),
    ("source", "sha256:" + "a" * 63),
    ("parse", "../parse"),
    ("parse", "/tmp/parse"),
    ("parse", r"C:\parse"),
    ("block", ".."),
    ("block", "../p0-b01"),
    ("quote", " \n\t "),
])
def test_evidence_rejects_unresolvable_references_and_empty_quotes(field, value):
    """Reject unsafe references and quotes without visible text."""
    evidence = deepcopy(achievement_record()["evidence"][0])
    evidence[field] = value

    with pytest.raises(ValidationError):
        Evidence.model_validate(evidence)


def test_verification_requires_human_and_timezone():
    """Require human verification and a timezone-aware timestamp."""
    with pytest.raises(ValidationError):
        Verification(by="agent", at=TIMESTAMP, sealed=HASH)
    with pytest.raises(ValidationError):
        Verification(by="human", at="2025-01-12T09:30:00", sealed=HASH)


@pytest.mark.parametrize("bbox", [
    [0, 0, 1],
    [0, 0, 1, 1, 1],
    [-0.1, 0, 1, 1],
    [0, 0, 1.01, 1],
    [0.8, 0, 0.2, 1],
    [0, 0.8, 1, 0.2],
    [float("nan"), 0, 1, 1],
    [0, 0, float("inf"), 1],
])
def test_block_rejects_invalid_bounding_boxes(bbox):
    """Reject malformed, out-of-range, and unordered bounding boxes."""
    with pytest.raises(ValidationError):
        ParsedBlock(id="p0-b01", page=0, bbox=bbox, type="text", text="award")


@pytest.mark.parametrize("field,value", [("page", -1), ("page", True), ("conf", -0.1), ("conf", 1.1)])
def test_block_rejects_invalid_page_and_confidence(field, value):
    """Reject invalid page indices and confidence values."""
    data = {"id": "p0-b01", "page": 0, "bbox": [0, 0, 1, 1], "type": "text", "text": "award"}
    data[field] = value
    with pytest.raises(ValidationError):
        ParsedBlock.model_validate(data)


def test_non_text_block_and_missing_confidence_are_supported():
    """Allow non-text blocks without a confidence score."""
    block = ParsedBlock(id="p0-b01", page=0, bbox=[0, 0, 1, 1], type="image", text="")
    assert block.conf is None


def test_source_and_parse_metadata_keep_known_machine_fields_typed():
    """Validate source and parse metadata field types."""
    source = SourceMetadata(
        hash=HASH,
        original_filename="国家奖学金证书.pdf",
        imported_at=TIMESTAMP,
        mime_type="application/pdf",
        size_bytes=42,
        origin="manual import",
        sensitive=True,
    )
    meta = ParseMeta(
        parse_id="p_20250112_093045",
        source=source.hash,
        engine="mineru-api",
        version="4.0",
        params={"language": "ch"},
        parsed_at=TIMESTAMP,
        remote=True,
    )
    assert source.original_filename == "国家奖学金证书.pdf"
    assert meta.params == {"language": "ch"}


def test_payload_rejects_kind_drift_and_implicit_string_coercion():
    """Reject unknown achievement kinds and implicit type coercion."""
    data = achievement_record()["data"]
    for change in ({"kind": "prize"}, {"level_raw": 2}, {"title": ""}, {"normalized_level": "second"}):
        with pytest.raises(ValidationError):
            AchievementData.model_validate(data | change)
