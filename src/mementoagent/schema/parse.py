"""Schemas for immutable parser snapshots."""

from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, field_validator

from .envelope import HashId, SafeIdentifier, Timestamp


class ParseMeta(BaseModel):
    """Metadata describing one immutable parse attempt."""

    model_config = ConfigDict(extra="forbid")

    parse_id: SafeIdentifier
    source: HashId
    engine: StrictStr = Field(min_length=1)
    version: StrictStr = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    parsed_at: Timestamp


class ParsedBlock(BaseModel):
    """Normalised block emitted by a document parser."""

    model_config = ConfigDict(extra="forbid")

    id: SafeIdentifier
    page: StrictInt = Field(ge=0)
    bbox: list[StrictFloat] = Field(min_length=4, max_length=4)
    type: StrictStr = Field(min_length=1)
    text: StrictStr
    conf: StrictFloat | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[float]) -> list[float]:
        """Validate normalized and ordered bounding-box coordinates.

        Args:
            value: Coordinates in ``[x0, y0, x1, y1]`` order.

        Returns:
            The unchanged coordinate list.

        Raises:
            ValueError: If coordinates are outside the page or unordered.
        """
        if any(not isfinite(coordinate) or coordinate < 0.0 or coordinate > 1.0 for coordinate in value):
            raise ValueError("bbox coordinates must be between 0 and 1")
        if value[0] > value[2] or value[1] > value[3]:
            raise ValueError("bbox must have x0 <= x1 and y0 <= y1")
        return value
