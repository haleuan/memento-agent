"""Tests for the common schema types."""

from typing import Literal

import pytest
from pydantic import ValidationError

from mementoagent.schema import PartialDate


@pytest.mark.parametrize(
    ("year", "month", "day", "precision"),
    [
        (2024, None, None, "year"),
        (2024, 10, None, "month"),
        (2024, 10, 15, "day"),
    ],
)
def test_partial_date_valid_precision(
    year: int,
    month: int | None,
    day: int | None,
    precision: Literal["year", "month", "day"],
) -> None:
    """Accept dates whose fields match the declared precision."""
    result = PartialDate(year=year, month=month, day=day, precision=precision)

    assert result.year == year
    assert result.month == month
    assert result.day == day
    assert result.precision == precision


@pytest.mark.parametrize(
    ("year", "month", "day", "precision"),
    [
        (2024, None, None, "month"),
        (2024, None, 15, "day"),
        (2024, 10, None, "day"),
    ],
)
def test_partial_date_rejects_missing_precision_fields(
    year: int,
    month: int | None,
    day: int | None,
    precision: Literal["year", "month", "day"],
) -> None:
    """Reject dates missing fields required by their precision."""
    with pytest.raises(ValidationError):
        PartialDate(year=year, month=month, day=day, precision=precision)


@pytest.mark.parametrize(
    ("month", "day", "precision"),
    [(1, None, "year"), (None, 1, "year"), (1, 1, "year"), (1, 1, "month")],
)
def test_partial_date_rejects_fields_beyond_precision(
    month: int | None, day: int | None, precision: str
) -> None:
    """Reject values that claim more date detail than their precision."""
    with pytest.raises(ValidationError):
        PartialDate.model_validate(
            {"year": 2024, "month": month, "day": day, "precision": precision}
        )


@pytest.mark.parametrize("field", ["year", "month", "day"])
@pytest.mark.parametrize("value", [True, "1", 1.0])
def test_partial_date_rejects_non_integer_types(field: str, value: object) -> None:
    """Reject coercible values instead of silently changing their types."""
    data: dict[str, object] = {"year": 2024, "month": 1, "day": 1, "precision": "day"}
    data[field] = value

    with pytest.raises(ValidationError):
        PartialDate.model_validate(data)


def test_partial_date_rejects_extra_fields() -> None:
    """Reject metadata that is outside the partial-date contract."""
    with pytest.raises(ValidationError):
        PartialDate.model_validate({"year": 2024, "precision": "year", "quarter": 1})


def test_partial_date_accepts_leap_day() -> None:
    """Preserve a valid leap day without losing precision."""
    result = PartialDate(year=2024, month=2, day=29, precision="day")

    assert str(result) == "2024-02-29"


@pytest.mark.parametrize("year", [1899, 2101])
def test_partial_date_rejects_year_outside_allowed_range(year: int) -> None:
    """Reject years outside the supported 1900 through 2100 range."""
    with pytest.raises(ValidationError):
        PartialDate(year=year, precision="year")


@pytest.mark.parametrize("month", [0, 13])
def test_partial_date_rejects_month_outside_allowed_range(month: int) -> None:
    """Reject month numbers outside the calendar range."""
    with pytest.raises(ValidationError):
        PartialDate(year=2024, month=month, precision="month")


@pytest.mark.parametrize(
    ("year", "month", "day"),
    [
        (2023, 2, 29),
        (2024, 2, 30),
        (2024, 4, 31),
    ],
)
def test_partial_date_rejects_invalid_calendar_day(
    year: int,
    month: int,
    day: int,
) -> None:
    """Reject days that do not exist in the specified calendar month."""
    with pytest.raises(ValidationError):
        PartialDate(year=year, month=month, day=day, precision="day")


@pytest.mark.parametrize(
    ("date", "expected_text", "expected_key"),
    [
        (PartialDate(year=2024, precision="year"), "2024", (2024, 1, 1)),
        (
            PartialDate(year=2024, month=10, precision="month"),
            "2024-10",
            (2024, 10, 1),
        ),
        (
            PartialDate(year=2024, month=10, day=15, precision="day"),
            "2024-10-15",
            (2024, 10, 15),
        ),
    ],
)
def test_partial_date_formats_and_sortable_key(
    date: PartialDate,
    expected_text: str,
    expected_key: tuple[int, int, int],
) -> None:
    """Format each precision and provide its comparison tuple."""
    assert str(date) == expected_text
    assert date.to_sortable_key() == expected_key
