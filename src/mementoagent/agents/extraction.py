"""Extract structured achievement data from a parse snapshot."""

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from mementoagent.schema import AchievementItem, HashId, ParseSnapshot

from .base import BaseAgent
from .harness import AgentHarness, AgentHarnessError


class AchievementExtractionError(ValueError):
    """Raised when a provider response cannot produce an achievement draft."""


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


_EXTRACTION_INSTRUCTIONS = """Extract one achievement from the supplied parsed document.
Use only facts explicitly supported by the document. Preserve names, titles,
organizations, levels, and certificate numbers as written. Leave optional
fields null when the document does not state them. Do not infer missing facts.
Leave data.description null because it is written by the user later.
If a concise description draft can be safely based on the document facts,
return it as description_suggestion with a rationale that identifies what the
user still needs to confirm. Do not invent personal responsibilities, impact,
metrics, or other facts. Return null when no safe suggestion is possible.
"""


class AchievementExtractor(BaseAgent[ParseSnapshot, AchievementExtraction]):
    """Extract an in-memory achievement draft with the shared harness."""

    name = "achievement_extractor"
    description = "Extract one document-supported achievement."
    instructions = _EXTRACTION_INSTRUCTIONS
    output_type = AchievementExtraction

    def __init__(self, harness: AgentHarness) -> None:
        """Initialize the extractor.

        Args:
            harness: Shared Agent runtime used to execute this task.
        """
        self._harness = harness

    def build_input(self, value: ParseSnapshot) -> str:
        """Return the complete parsed document for the extraction task.

        Args:
            value: Parsed source content to extract from.

        Returns:
            The original parser output without additional formatting.
        """
        return value.content

    def extract(self, snapshot: ParseSnapshot) -> AchievementDraft:
        """Extract an achievement draft from a parse snapshot.

        Args:
            snapshot: Parsed source content and its source hash metadata.

        Returns:
            An unpersisted draft whose source is copied from the snapshot.

        Raises:
            AchievementExtractionError: If the harness cannot produce a usable
                structured achievement.
        """
        try:
            extraction = self._harness.run(self, snapshot)
        except AgentHarnessError as error:
            raise AchievementExtractionError(str(error)) from error

        return AchievementDraft(
            data=extraction.data,
            source=snapshot.metadata.source,
            description_suggestion=extraction.description_suggestion,
        )
