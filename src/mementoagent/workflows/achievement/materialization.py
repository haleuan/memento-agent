"""Materialize reviewed achievement drafts as persisted record envelopes."""

from datetime import datetime

from mementoagent.schema import (
    ACHIEVEMENT_SCHEMA_VERSION,
    AchievementItem,
    Evidence,
    RecordEnvelope,
    generate_record_id,
)

from .models import ReviewedAchievementDraft


class AchievementMaterializationError(ValueError):
    """Raised when a reviewed achievement cannot become a record."""


def materialize_achievement(
    reviewed: ReviewedAchievementDraft,
    *,
    record_id: str | None = None,
    created_at: str | None = None,
) -> RecordEnvelope[AchievementItem]:
    """Convert an approved reviewed draft into an in-memory record envelope.

    Args:
        reviewed: The in-memory result of the achievement review workflow.
        record_id: Optional deterministic identifier for callers and tests.
        created_at: Optional timezone-aware creation timestamp for callers and tests.

    Returns:
        A document-provenance achievement record with source-level evidence.

    Raises:
        AchievementMaterializationError: If the review was rejected or the
            resulting envelope violates the record schema.
    """
    if reviewed.status != "approved" or reviewed.reviewed_data is None:
        raise AchievementMaterializationError(
            "only an approved reviewed achievement can be materialized"
        )

    data = reviewed.reviewed_data.model_copy(deep=True)
    if reviewed.description is not None:
        data = data.model_copy(update={"description": reviewed.description})

    resolved_record_id = record_id or generate_record_id("ach")
    resolved_created_at = created_at or datetime.now().astimezone().isoformat()

    try:
        return RecordEnvelope[AchievementItem](
            id=resolved_record_id,
            schema=ACHIEVEMENT_SCHEMA_VERSION,
            provenance="document",
            created_at=resolved_created_at,
            occurred=None,
            data=data,
            evidence=[Evidence(source=reviewed.draft.source, supports=[])],
            verification=None,
        )
    except ValueError as error:
        raise AchievementMaterializationError(
            "reviewed achievement does not satisfy the record schema"
        ) from error
