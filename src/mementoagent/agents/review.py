"""Apply structured user review decisions to achievement drafts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from mementoagent.schema import AchievementItem

from .extraction import AchievementDraft


class AchievementReviewDecision(BaseModel):
    """A structured decision produced from the user's conversation."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "rejected"]
    data: AchievementItem | None = None
    description: StrictStr | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_decision(self) -> "AchievementReviewDecision":
        """Keep rejected and approved decisions unambiguous."""
        if self.status == "rejected":
            if self.data is not None or self.description is not None:
                raise ValueError(
                    "rejected decisions cannot include data or description"
                )
        elif self.data is not None and self.data.description is not None:
            raise ValueError("reviewed data description must remain separate")
        return self


class ReviewedAchievementDraft(BaseModel):
    """An in-memory achievement draft after a user's review decision."""

    model_config = ConfigDict(extra="forbid")

    draft: AchievementDraft
    status: Literal["approved", "rejected"]
    reviewed_data: AchievementItem | None = None
    description: StrictStr | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_reviewed_result(self) -> "ReviewedAchievementDraft":
        """Keep rejected results empty and descriptions separate from facts."""
        if self.status == "rejected":
            if self.reviewed_data is not None or self.description is not None:
                raise ValueError(
                    "rejected results cannot include reviewed data or description"
                )
        elif self.reviewed_data is None:
            raise ValueError("approved results require reviewed data")

        if (
            self.reviewed_data is not None
            and self.reviewed_data.description is not None
        ):
            raise ValueError("reviewed data description must remain separate")
        return self


def review_achievement_draft(
    draft: AchievementDraft,
    decision: AchievementReviewDecision,
) -> ReviewedAchievementDraft:
    """Apply one structured user review decision without persisting it.

    Args:
        draft: Original achievement draft returned by the extractor.
        decision: Structured result of the user's conversation with the agent.

    Returns:
        An in-memory review result retaining the original draft and, when
        approved, the final facts and optional user-authored description.

    Raises:
        ValueError: If the decision violates the review result contract.
    """
    original_draft = draft.model_copy(deep=True)
    if decision.status == "rejected":
        return ReviewedAchievementDraft(
            draft=original_draft,
            status="rejected",
        )

    reviewed_data = (decision.data or draft.data).model_copy(deep=True)
    return ReviewedAchievementDraft(
        draft=original_draft,
        status="approved",
        reviewed_data=reviewed_data,
        description=decision.description,
    )
