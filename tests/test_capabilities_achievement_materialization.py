"""Tests for achievement record materialization."""

from datetime import datetime
from pathlib import Path

from mementoagent.capabilities.achievement import (
    AchievementDraft,
    DescriptionSuggestion,
    materialize_achievement,
)
from mementoagent.schema import AchievementItem, RecordEnvelope
from mementoagent.validation import validate_record
from mementoagent.workspace import import_source, load_record, save_record

SOURCE = "sha256:" + "a" * 64
RECORD_ID = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
CREATED_AT = "2025-01-12T09:30:00+08:00"


def make_draft(
    *,
    organization: str | None = "Example University",
    description_suggestion: DescriptionSuggestion | None = None,
) -> AchievementDraft:
    """Build an extracted achievement draft."""
    return AchievementDraft(
        data=AchievementItem(
            kind="certificate",
            title="Certificate of Completion",
            organization=organization,
            certificate_number="CERT-123",
        ),
        source=SOURCE,
        description_suggestion=description_suggestion,
    )


def test_materialize_confirmed_data_with_source_evidence() -> None:
    """Create a document-provenance envelope without field-level claims."""
    record = materialize_achievement(
        make_draft(),
        make_draft().data,
        record_id=RECORD_ID,
        created_at=CREATED_AT,
    )

    assert isinstance(record, RecordEnvelope)
    assert record.id == RECORD_ID
    assert record.schema_version == "achievement/1"
    assert record.provenance == "document"
    assert record.created_at == CREATED_AT
    assert record.occurred is None
    assert record.verification is None
    assert record.evidence[0].source == SOURCE
    assert record.evidence[0].supports == []
    assert record.data.description is None


def test_materialize_copies_user_description_without_mutating_input() -> None:
    """Persist a confirmed description while preserving input data."""
    draft = make_draft()
    data = draft.data.model_copy(update={"description": "Completed the program."})

    record = materialize_achievement(
        draft,
        data,
        record_id=RECORD_ID,
        created_at=CREATED_AT,
    )

    assert record.data.description == "Completed the program."
    assert draft.data.description is None


def test_materialize_preserves_correction_and_missing_organization() -> None:
    """Allow corrected facts and records without an organization."""
    draft = make_draft(organization=None)
    corrected = draft.data.model_copy(update={"title": "Corrected Certificate"})

    record = materialize_achievement(
        draft,
        corrected,
        record_id=RECORD_ID,
        created_at=CREATED_AT,
    )

    assert record.data.organization is None
    assert record.data.title == "Corrected Certificate"


def test_materialize_generates_valid_identity_and_timestamp() -> None:
    """Generate an achievement ULID and timezone-aware timestamp by default."""
    draft = make_draft()
    record = materialize_achievement(draft, draft.data)

    assert record.id.startswith("ach_")
    assert len(record.id.removeprefix("ach_")) == 26
    parsed = datetime.fromisoformat(record.created_at)
    assert parsed.tzinfo is not None


def test_materialize_round_trips_and_validates_source(tmp_path: Path) -> None:
    """Persist and validate a materialized record through existing APIs."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    source_path = tmp_path / "certificate.pdf"
    source_path.write_bytes(b"certificate")
    source = import_source(workspace_root, source_path)
    draft = make_draft().model_copy(update={"source": source})

    record = materialize_achievement(
        draft,
        draft.data,
        record_id=RECORD_ID,
        created_at=CREATED_AT,
    )
    assert validate_record(workspace_root, record) == []

    path = save_record(workspace_root, record)
    assert load_record(path, AchievementItem) == record
