"""Schemas for achievement records.

The values in this module intentionally retain the text extracted from a
source document.  In particular, ``level_raw`` is not normalised into a
canonical ranking; doing that would turn an extraction into an inference.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class AchievementData(BaseModel):
    """Payload for the first concrete record type."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["award", "paper", "project", "internship", "certificate"]
    title: StrictStr = Field(min_length=1)
    issuer: StrictStr = Field(min_length=1)
    level_raw: StrictStr = Field(min_length=1)
    notes: StrictStr | None = None
