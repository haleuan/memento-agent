"""Tests for standard-library record identifiers."""

import re

from mementoagent.schema import generate_record_id


def test_generate_record_id_returns_type_prefixed_ulid() -> None:
    """Generate an identifier accepted by the record ID contract."""
    record_id = generate_record_id("ach")

    assert re.fullmatch(r"ach_[0-7][0-9A-HJKMNP-TV-Z]{25}", record_id)


def test_generate_record_id_generates_distinct_values() -> None:
    """Use random entropy so consecutive record IDs do not collide."""
    assert generate_record_id("ach") != generate_record_id("ach")
