"""Extract structured achievement data from a parse snapshot."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    model_validator,
)

from mementoagent.providers import OpenAIProvider
from mementoagent.schema import AchievementItem, HashId, ParseSnapshot


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


class AchievementExtractor:
    """Extract an in-memory achievement draft with a structured provider."""

    def __init__(self, provider: OpenAIProvider, model: str) -> None:
        """Initialize the extractor.

        Args:
            provider: Provider that supports structured Pydantic responses.
            model: Model identifier passed to the provider.
        """
        self._provider = provider
        self._model = model

    def extract(self, snapshot: ParseSnapshot) -> AchievementDraft:
        """Extract an achievement draft from a parse snapshot.

        Args:
            snapshot: Parsed source content and its source hash metadata.

        Returns:
            An unpersisted draft whose source is copied from the snapshot.

        Raises:
            AchievementExtractionError: If the provider returns no usable
                structured achievement.
        """
        response = self._provider.parse(
            instructions=_EXTRACTION_INSTRUCTIONS,
            input=snapshot.content,
            model=self._model,
            text_format=AchievementExtraction,
        )
        if response.output_parsed is None:
            raise AchievementExtractionError(
                "provider returned no structured achievement"
            )

        try:
            extraction = AchievementExtraction.model_validate(response.output_parsed)
        except ValidationError as error:
            raise AchievementExtractionError(
                "provider returned an invalid achievement"
            ) from error

        return AchievementDraft(
            data=extraction.data,
            source=snapshot.metadata.source,
            description_suggestion=extraction.description_suggestion,
        )
