"""Common types for the Memento Agent schema."""

import calendar
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class PartialDate(BaseModel):
    """A date with variable precision (year, month, or day).

    This type captures dates as they appear in certificates and documents,
    which may specify only a year ("2024") or year-month ("2024-10") rather
    than a complete date.

    The agent should extract the date string as written and pass it to a
    deterministic parser, which will produce this structure. The agent should
    NOT guess or fill in missing month/day values.

    Examples:
        - Certificate states "2024": PartialDate(year=2024, precision="year")
        - Certificate states "October 2024": PartialDate(year=2024, month=10, precision="month")
        - Certificate states "2024-10-15": PartialDate(year=2024, month=10, day=15, precision="day")
    """

    model_config = ConfigDict(extra="forbid")

    year: StrictInt = Field(
        ge=1900, le=2100, description="Four-digit year. Must be between 1900 and 2100."
    )
    month: StrictInt | None = Field(
        default=None,
        ge=1,
        le=12,
        description="Month (1-12). Required when precision is 'month' or 'day'.",
    )
    day: StrictInt | None = Field(
        default=None,
        ge=1,
        le=31,
        description="Day of month (1-31). Required when precision is 'day'.",
    )
    precision: Literal["year", "month", "day"] = Field(
        description="The level of detail present in the original source. "
        "This determines which fields are meaningful."
    )

    @model_validator(mode="after")
    def validate_consistency(self) -> "PartialDate":
        """Ensure precision matches the presence of month and day fields."""
        if self.precision == "year" and (
            self.month is not None or self.day is not None
        ):
            raise ValueError("precision='year' does not allow month or day")
        if self.precision == "month" and self.month is None:
            raise ValueError("precision='month' requires month to be set")
        if self.precision == "month" and self.day is not None:
            raise ValueError("precision='month' does not allow day")
        if self.precision == "day" and (self.month is None or self.day is None):
            raise ValueError("precision='day' requires both month and day to be set")

        # Validate day range against calendar
        if self.day is not None and self.month is not None:
            max_day = calendar.monthrange(self.year, self.month)[1]
            if self.day > max_day:
                raise ValueError(
                    f"day must be between 1 and {max_day} for {self.year}-{self.month:02d}, "
                    f"got {self.day}"
                )

        return self

    def __str__(self) -> str:
        """Return ISO 8601-like string representation based on precision."""
        if self.precision == "year":
            return f"{self.year}"
        elif self.precision == "month":
            return f"{self.year}-{self.month:02d}"
        else:  # day
            return f"{self.year}-{self.month:02d}-{self.day:02d}"

    def to_sortable_key(self) -> tuple[int, int, int]:
        """Return a tuple suitable for sorting and comparison.

        Missing month/day are filled with 1 for the purpose of ordering.
        This is ONLY for comparison—the original precision is preserved.

        Examples:
            PartialDate(2024, precision="year").to_sortable_key() → (2024, 1, 1)
            PartialDate(2024, 10, precision="month").to_sortable_key() → (2024, 10, 1)
            PartialDate(2024, 10, 15, precision="day").to_sortable_key() → (2024, 10, 15)
        """
        return (
            self.year,
            self.month if self.month is not None else 1,
            self.day if self.day is not None else 1,
        )
