"""Schemas for persisted parse snapshots."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr
from pydantic.types import StringConstraints

from .envelope import HashId, Timestamp


ParseId = Annotated[
    StrictStr,
    StringConstraints(pattern=r"^parse_[0-9a-f]{32}$"),
]


class ParseSnapshotMetadata(BaseModel):
    """Metadata that identifies a successful parse snapshot."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["parse/1"] = Field(
        alias="schema",
        description="Version of the persisted parse snapshot metadata format.",
    )
    parse_id: ParseId = Field(
        description="Unique identifier in the format `parse_<32 lowercase hex digits>`.",
    )
    source: HashId = Field(
        description="Content hash of the original source file.",
    )
    parser: StrictStr = Field(
        min_length=1,
        description="Name of the parser that produced this snapshot.",
    )
    parser_version: StrictStr = Field(
        min_length=1,
        description="Version of the parser that produced this snapshot.",
    )
    created_at: Timestamp = Field(
        description="When this parse snapshot was created, with timezone.",
    )


class ParseSnapshot(BaseModel):
    """Metadata and complete Markdown output for a parse snapshot."""

    model_config = ConfigDict(extra="forbid")

    metadata: ParseSnapshotMetadata
    content: StrictStr
