"""Tests for achievement record payloads."""

import pytest
from pydantic import ValidationError

from mementoagent.schema import AchievementItem, AchievementReference


@pytest.mark.parametrize(
    "reference_type", ["doi", "github", "pdf", "website", "certificate_id", "arxiv"]
)
def test_achievement_reference_accepts_links_and_identifiers(
    reference_type: str,
) -> None:
    """Accept supported reference types without requiring an HTTP URL."""
    result = AchievementReference.model_validate(
        {"type": reference_type, "url": "document-identifier"}
    )

    assert result.url == "document-identifier"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"type": "doi"},
        {"url": "identifier"},
        {"type": "unknown", "url": "identifier"},
        {"type": "doi", "url": ""},
        {"type": "doi", "url": 123},
        {"type": "doi", "url": "identifier", "label": "extra"},
    ],
)
def test_achievement_reference_rejects_invalid_data(data: dict[str, object]) -> None:
    """Reject incomplete, untyped, or extra reference metadata."""
    with pytest.raises(ValidationError):
        AchievementReference.model_validate(data)


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
    assert result.certificate_number is None
    assert result.description is None
    assert result.collaborators is None
    assert result.references is None
    assert result.tags is None


def test_achievement_item_accepts_certificate_number() -> None:
    """Store a certificate number as a structured achievement attribute."""
    result = AchievementItem(
        kind="certificate",
        title="Certificate of Completion",
        organization="Memento Institute",
        certificate_number="CERT-123",
    )

    assert result.certificate_number == "CERT-123"


def test_achievement_item_rejects_empty_certificate_number() -> None:
    """Reject an empty certificate number when one is provided."""
    with pytest.raises(ValidationError):
        AchievementItem(
            kind="certificate",
            title="Certificate of Completion",
            organization="Memento Institute",
            certificate_number="",
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "kind",
        "title",
        "organization",
        "level_raw",
        "certificate_number",
        "description",
        "collaborators",
        "references",
        "tags",
    ],
)
def test_achievement_item_fields_have_descriptions(field_name: str) -> None:
    """Ensure each achievement field retains its user-facing description."""
    assert AchievementItem.model_fields[field_name].description is not None
