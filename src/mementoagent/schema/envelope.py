"""Generic record envelope and provenance/evidence schemas."""

from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictStr, field_validator
from pydantic.types import StringConstraints


_HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"
_ID_PATTERN = r"^[a-z][a-z0-9-]*_[0-7][0-9A-HJKMNP-TV-Z]{25}$"
_SCHEMA_PATTERN = r"^[a-z][a-z0-9-]*/[1-9][0-9]*$"

HashId = Annotated[StrictStr, StringConstraints(pattern=_HASH_PATTERN)]
RecordId = Annotated[StrictStr, StringConstraints(pattern=_ID_PATTERN)]
SchemaVersion = Annotated[StrictStr, StringConstraints(pattern=_SCHEMA_PATTERN)]
SafeIdentifier = Annotated[
    StrictStr, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
]


def _validate_timestamp(value: str) -> str:
    """Validate an ISO timestamp without changing its original representation."""
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("must be an ISO 8601 timestamp with timezone") from error
    if "T" not in value or timestamp.tzinfo is None:
        raise ValueError("must be an ISO 8601 timestamp with timezone")
    return value


Timestamp = Annotated[StrictStr, AfterValidator(_validate_timestamp)]


class Occurred(BaseModel):
    """Optional event date/range, kept as strings to support partial dates."""

    model_config = ConfigDict(extra="forbid")

    start: StrictStr | None = None
    end: StrictStr | None = None


class Evidence(BaseModel):
    """A pointer from a record claim to an immutable parsed source block."""

    model_config = ConfigDict(extra="forbid")

    source: HashId
    parse: SafeIdentifier
    block: SafeIdentifier
    supports: list[StrictStr] = Field(default_factory=list)
    quote: StrictStr = Field(min_length=1)

    @field_validator("quote")
    @classmethod
    def validate_quote(cls, value: str) -> str:
        """Reject evidence quotes that contain only whitespace.

        Args:
            value: Quote text supplied by the record.

        Returns:
            The unchanged quote text.

        Raises:
            ValueError: If the quote contains no visible text.
        """
        if not value.strip():
            raise ValueError("quote must contain non-whitespace text")
        return value


class Verification(BaseModel):
    """Human review seal for the critical fields of a record."""

    model_config = ConfigDict(extra="forbid")

    by: Literal["human"]
    at: Timestamp
    sealed: HashId


RecordData = TypeVar("RecordData", bound=BaseModel)


class RecordEnvelope(BaseModel, Generic[RecordData]):
    """Common metadata envelope around a type-specific payload."""

    model_config = ConfigDict(extra="forbid")

    id: RecordId
    schema_version: SchemaVersion = Field(alias="schema")
    provenance: Literal["document", "user", "agent"]
    created_at: Timestamp
    occurred: Occurred | None = None
    data: RecordData
    evidence: list[Evidence] = Field(default_factory=list)
    verification: Verification | None = None
