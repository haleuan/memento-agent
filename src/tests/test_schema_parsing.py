"""Tests for parse snapshot schemas."""

import pytest
from pydantic import ValidationError

from mementoagent.schema import ParseSnapshot, ParseSnapshotMetadata


VALID_HASH = "sha256:" + "a" * 64
VALID_PARSE_ID = "parse_" + "b" * 32
CREATED_AT = "2025-01-12T09:30:00+08:00"


def make_metadata(**overrides: object) -> ParseSnapshotMetadata:
    """Build valid parse metadata, applying provided field overrides."""
    fields: dict[str, object] = {
        "schema": "parse/1",
        "parse_id": VALID_PARSE_ID,
        "source": VALID_HASH,
        "parser": "example-parser",
        "parser_version": "1.0.0",
        "created_at": CREATED_AT,
    }
    fields.update(overrides)
    return ParseSnapshotMetadata.model_validate(fields)


def test_parse_snapshot_metadata_accepts_contract_and_schema_alias() -> None:
    """Accept metadata and serialize the schema version under its TOML key."""
    metadata = make_metadata()

    assert metadata.schema_version == "parse/1"
    assert metadata.model_dump(by_alias=True)["schema"] == "parse/1"
    assert metadata.parse_id == VALID_PARSE_ID
    assert metadata.source == VALID_HASH


def test_parse_snapshot_metadata_requires_schema_version() -> None:
    """Require an explicit format version in persisted parse metadata."""
    fields = {
        "parse_id": VALID_PARSE_ID,
        "source": VALID_HASH,
        "parser": "example-parser",
        "parser_version": "1.0.0",
        "created_at": CREATED_AT,
    }

    with pytest.raises(ValidationError):
        ParseSnapshotMetadata.model_validate(fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"parse_id": "parse_bad"},
        {"source": "sha256:bad"},
        {"parser": ""},
        {"parser_version": ""},
        {"created_at": "2025-01-12T09:30:00"},
        {"unexpected": "value"},
        {"schema": "parse/2"},
    ],
)
def test_parse_snapshot_metadata_rejects_invalid_fields(
    overrides: dict[str, object],
) -> None:
    """Reject malformed identifiers, metadata values, and unknown fields."""
    fields: dict[str, object] = {
        "schema": "parse/1",
        "parse_id": VALID_PARSE_ID,
        "source": VALID_HASH,
        "parser": "example-parser",
        "parser_version": "1.0.0",
        "created_at": CREATED_AT,
    }
    fields.update(overrides)

    with pytest.raises(ValidationError):
        ParseSnapshotMetadata.model_validate(fields)


def test_parse_snapshot_preserves_content() -> None:
    """Keep parsed text unchanged in the snapshot model."""
    content = "# 奖状\n\n---\nAwarded to: 林\n"

    snapshot = ParseSnapshot(metadata=make_metadata(), content=content)

    assert snapshot.content == content


def test_parse_snapshot_rejects_unknown_fields() -> None:
    """Reject fields outside the persisted snapshot contract."""
    with pytest.raises(ValidationError):
        ParseSnapshot.model_validate(
            {"metadata": make_metadata(), "content": "text", "extra": "value"}
        )
