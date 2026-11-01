"""Tests for achievement record materialization."""

from datetime import datetime
from pathlib import Path

import pytest

from mementoagent.schema import AchievementItem, RecordEnvelope
from mementoagent.validation import validate_record
from mementoagent.workflows.achievement import (
    AchievementDraft,
    AchievementMaterializationError,
    DescriptionSuggestion,
    ReviewedAchievementDraft,
    materialize_achievement,
)
from mementoagent.workspace import import_source, load_record, save_record

SOURCE = "sha256:" + "a" * 64
RECORD_ID = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
CREATED_AT = "2025-01-12T09:30:00+08:00"


def make_reviewed(
    *,
    organization: str | None = "Example University",
    description: str | None = None,
    status: str = "approved",
) -> ReviewedAchievementDraft:
    """Build a reviewed achievement for materialization tests."""
    draft = AchievementDraft(
        data=AchievementItem(
            kind="certificate",
            title="Certificate of Completion",
            organization=organization,
            certificate_number="CERT-123",
        ),
        source=SOURCE,
        description_suggestion=DescriptionSuggestion(
            text="Completed a recognized certificate.",
            rationale="The source states the certificate title.",
        ),
    )
    if status == "rejected":
        return ReviewedAchievementDraft(draft=draft, status="rejected")
    reviewed_data = draft.data.model_copy()
    return ReviewedAchievementDraft(
        draft=draft,
        status="approved",
        reviewed_data=reviewed_data,
        description=description,
    )


def test_materialize_approved_review_with_source_evidence() -> None:
    """Create a document-provenance envelope without field-level claims."""
    reviewed = make_reviewed()

    record = materialize_achievement(
        reviewed,
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


def test_materialize_copies_accepted_description_without_mutating_review() -> None:
    """Persist an accepted description while preserving the reviewed draft."""
    reviewed = make_reviewed(description="Completed the certificate program.")
    original_data = reviewed.reviewed_data.model_copy(deep=True)

    record = materialize_achievement(
        reviewed,
        record_id=RECORD_ID,
        created_at=CREATED_AT,
    )

    assert record.data.description == "Completed the certificate program."
    assert reviewed.reviewed_data == original_data
    assert reviewed.draft.description_suggestion is not None


def test_materialize_preserves_correction_and_missing_organization() -> None:
    """Allow corrected facts and records without an organization."""
    reviewed = make_reviewed(organization=None)

    record = materialize_achievement(
        reviewed,
        record_id=RECORD_ID,
        created_at=CREATED_AT,
    )

    assert record.data.organization is None
    assert record.data.certificate_number == "CERT-123"


def test_materialize_rejects_rejected_review() -> None:
    """Reject a review result that cannot become a persisted record."""
    with pytest.raises(AchievementMaterializationError):
        materialize_achievement(
            make_reviewed(status="rejected"),
            record_id=RECORD_ID,
            created_at=CREATED_AT,
        )


def test_materialize_generates_valid_identity_and_timestamp() -> None:
    """Generate an achievement ULID and timezone-aware timestamp by default."""
    record = materialize_achievement(make_reviewed())

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
    reviewed = make_reviewed()
    reviewed = reviewed.model_copy(
        update={"draft": reviewed.draft.model_copy(update={"source": source})}
    )

    record = materialize_achievement(
        reviewed,
        record_id=RECORD_ID,
        created_at=CREATED_AT,
    )
    assert validate_record(workspace_root, record) == []

    path = save_record(workspace_root, record)
    assert load_record(path, AchievementItem) == record
