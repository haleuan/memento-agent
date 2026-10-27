"""Schema for imported immutable source metadata."""

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from .envelope import HashId, Timestamp


class SourceMetadata(BaseModel):
    """Sidecar metadata stored alongside a content-addressed source file."""

    model_config = ConfigDict(extra="forbid")

    hash: HashId
    original_filename: StrictStr = Field(min_length=1)
    imported_at: Timestamp
    mime_type: StrictStr = Field(min_length=1)
    size_bytes: StrictInt = Field(ge=0)
    origin: StrictStr = Field(min_length=1)
    sensitive: StrictBool
