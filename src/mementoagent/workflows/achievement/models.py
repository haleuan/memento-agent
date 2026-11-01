"""Ephemeral models used by the achievement workflows."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from mementoagent.schema import AchievementItem, HashId


class DescriptionSuggestion(BaseModel):
    """A user-editable description candidate derived from source facts."""

    model_config = ConfigDict(extra="forbid")

    text: StrictStr = Field(min_length=1)
    rationale: StrictStr = Field(min_length=1)


class AchievementExtraction(BaseModel):
    """Structured fields extracted from one parse snapshot."""

    model_config = ConfigDict(extra="forbid")

    data: AchievementItem
    description_suggestion: DescriptionSuggestion | None = None

    @model_validator(mode="after")
    def reject_user_description(self) -> "AchievementExtraction":
        """Keep the user-authored description outside document extraction."""
        if self.data.description is not None:
            raise ValueError("description must be left for the user")
        return self


class AchievementDraft(BaseModel):
    """An unpersisted achievement extracted from a source snapshot."""

    model_config = ConfigDict(extra="forbid")

    data: AchievementItem
    source: HashId
    description_suggestion: DescriptionSuggestion | None = None

    @model_validator(mode="after")
    def reject_user_description(self) -> "AchievementDraft":
        """Keep the user-authored description outside document extraction."""
        if self.data.description is not None:
            raise ValueError("description must be left for the user")
        return self


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
