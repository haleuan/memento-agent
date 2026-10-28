"""Tests for achievement record payloads."""

import pytest
from pydantic import ValidationError

from mementoagent.schema import AchievementItem


def test_achievement_item_accepts_required_fields() -> None:
    """Construct an achievement from its required kind, title, and organization."""
    result = AchievementItem(
        kind="project",
        title="Open Source Contribution",
        organization="Memento Agent",
    )

    assert result.kind == "project"
    assert result.title == "Open Source Contribution"
    assert result.organization == "Memento Agent"


def test_achievement_item_rejects_unknown_fields() -> None:
    """Reject payload keys that are outside the strict achievement schema."""
    with pytest.raises(ValidationError):
        AchievementItem.model_validate(
            {
                "kind": "project",
                "title": "Open Source Contribution",
                "organization": "Memento Agent",
                "unknown_field": "unexpected",
            }
        )


def test_achievement_item_optional_fields_default_to_none() -> None:
    """Leave optional narrative and metadata fields unset by default."""
    result = AchievementItem(
        kind="award",
        title="First Prize",
        organization="Competition Committee",
    )

    assert result.level_raw is None
    assert result.description is None
    assert result.collaborators is None
    assert result.references is None
    assert result.tags is None


@pytest.mark.parametrize(
    "field_name",
    [
        "kind",
        "title",
        "organization",
        "level_raw",
        "description",
        "collaborators",
        "references",
        "tags",
    ],
)
def test_achievement_item_fields_have_descriptions(field_name: str) -> None:
    """Ensure each achievement field retains its user-facing description."""
    assert AchievementItem.model_fields[field_name].description is not None
