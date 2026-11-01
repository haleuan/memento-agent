"""Materialize reviewed achievement data as record envelopes."""

from datetime import datetime

from mementoagent.schema import (
    ACHIEVEMENT_SCHEMA_VERSION,
    AchievementItem,
    Evidence,
    RecordEnvelope,
    generate_record_id,
)

from .models import AchievementDraft


class AchievementMaterializationError(ValueError):
    """Raised when an achievement cannot become a record."""


def materialize_achievement(
    draft: AchievementDraft,
    data: AchievementItem,
    *,
    record_id: str | None = None,
    created_at: str | None = None,
) -> RecordEnvelope[AchievementItem]:
    """Convert confirmed achievement data into an in-memory record envelope.

    Args:
        draft: Original extracted draft containing source provenance.
        data: Complete facts confirmed or corrected by the user-facing Agent.
        record_id: Optional deterministic identifier for callers and tests.
        created_at: Optional timezone-aware creation timestamp for callers and tests.

    Returns:
        A document-provenance achievement record with source-level evidence.

    Raises:
        AchievementMaterializationError: If the resulting envelope violates
            the record schema.
    """
    resolved_record_id = record_id or generate_record_id("ach")
    resolved_created_at = created_at or datetime.now().astimezone().isoformat()

    try:
        return RecordEnvelope[AchievementItem](
            id=resolved_record_id,
            schema=ACHIEVEMENT_SCHEMA_VERSION,
            provenance="document",
            created_at=resolved_created_at,
            occurred=None,
            data=data.model_copy(deep=True),
            evidence=[Evidence(source=draft.source, supports=[])],
            verification=None,
        )
    except ValueError as error:
        raise AchievementMaterializationError(
            "achievement data does not satisfy the record schema"
        ) from error
