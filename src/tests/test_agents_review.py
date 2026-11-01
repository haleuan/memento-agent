"""Tests for conversational achievement draft review."""

import pytest
from pydantic import ValidationError

from mementoagent.schema import AchievementItem
from mementoagent.workflows.achievement import (
    AchievementDraft,
    AchievementReviewDecision,
    DescriptionSuggestion,
    ReviewedAchievementDraft,
    review_achievement_draft,
)

SOURCE = "sha256:" + "a" * 64


def make_draft(
    *,
    suggestion: DescriptionSuggestion | None = None,
    **data: object,
) -> AchievementDraft:
    """Build a valid achievement draft for review tests."""
    return AchievementDraft(
        data=AchievementItem(
            kind="award",
            title="Graduate Scholarship",
            organization="Example University",
            **data,
        ),
        source=SOURCE,
        description_suggestion=suggestion,
    )


def test_approval_uses_original_data_and_keeps_source() -> None:
    """Approve a draft without changes while retaining its source identity."""
    draft = make_draft(level_raw="First Prize")
    result = review_achievement_draft(
        draft,
        AchievementReviewDecision(status="approved"),
    )

    assert result.status == "approved"
    assert result.reviewed_data == draft.data
    assert result.draft == draft
    assert result.draft.source == SOURCE
    assert result.description is None


def test_approval_keeps_original_when_facts_are_corrected() -> None:
    """Retain extracted and user-corrected facts as separate values."""
    draft = make_draft(level_raw="First Prize")
    corrected = draft.data.model_copy(
        update={"organization": "Example Graduate School"}
    )

    result = review_achievement_draft(
        draft,
        AchievementReviewDecision(status="approved", data=corrected),
    )

    assert result.draft.data.organization == "Example University"
    assert result.reviewed_data is not None
    assert result.reviewed_data.organization == "Example Graduate School"
    assert result.draft.source == SOURCE


def test_accept_description_suggestion_as_separate_user_description() -> None:
    """Keep an accepted suggestion outside reviewed document facts."""
    suggestion = DescriptionSuggestion(
        text="Received the Graduate Scholarship First Prize at Example University.",
        rationale="Restates only the award and level documented in the certificate.",
    )
    draft = make_draft(suggestion=suggestion, level_raw="First Prize")

    result = review_achievement_draft(
        draft,
        AchievementReviewDecision(status="approved", description=suggestion.text),
    )

    assert result.description == suggestion.text
    assert result.reviewed_data is not None
    assert result.reviewed_data.description is None
    assert result.draft.description_suggestion == suggestion


def test_custom_description_without_suggestion_is_allowed() -> None:
    """Allow the agent to submit a user description when no suggestion exists."""
    result = review_achievement_draft(
        make_draft(),
        AchievementReviewDecision(
            status="approved", description="User-supplied description"
        ),
    )

    assert result.description == "User-supplied description"


def test_skip_description_keeps_approved_facts() -> None:
    """Approve facts while leaving the optional description empty."""
    result = review_achievement_draft(
        make_draft(
            suggestion=DescriptionSuggestion(
                text="Suggested description", rationale="Source facts"
            )
        ),
        AchievementReviewDecision(status="approved"),
    )

    assert result.status == "approved"
    assert result.description is None
    assert result.reviewed_data is not None


def test_rejection_returns_empty_review_result() -> None:
    """Represent user rejection without raising or creating record data."""
    draft = make_draft()
    result = review_achievement_draft(
        draft,
        AchievementReviewDecision(status="rejected"),
    )

    assert result == ReviewedAchievementDraft(draft=draft, status="rejected")
    assert result.reviewed_data is None
    assert result.description is None


def test_rejected_decision_cannot_include_values() -> None:
    """Reject ambiguous decisions that mix rejection with submitted values."""
    with pytest.raises(ValidationError, match="rejected decisions"):
        AchievementReviewDecision(status="rejected", description="Description")


def test_reviewed_data_cannot_contain_description() -> None:
    """Keep descriptions outside document fact data after review."""
    with pytest.raises(ValidationError, match="description"):
        AchievementReviewDecision(
            status="approved",
            data=AchievementItem(
                kind="award",
                title="Award",
                organization="Institution",
                description="User description",
            ),
        )


def test_extra_decision_fields_are_rejected() -> None:
    """Keep the agent-to-review contract strict."""
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AchievementReviewDecision(status="approved", confirmed=True)  # type: ignore[call-arg]


def test_review_does_not_mutate_input_draft() -> None:
    """Apply corrections to a copied result rather than the original draft."""
    draft = make_draft()
    corrected = draft.data.model_copy(update={"title": "Corrected title"})

    result = review_achievement_draft(
        draft,
        AchievementReviewDecision(status="approved", data=corrected),
    )

    assert draft.data.title == "Graduate Scholarship"
    assert result.reviewed_data is not None
    assert result.reviewed_data.title == "Corrected title"
