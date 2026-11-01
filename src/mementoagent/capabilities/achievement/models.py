"""Transient models used by achievement capabilities."""

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
