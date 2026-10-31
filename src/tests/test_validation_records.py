"""Tests for source-level record validation."""

from pathlib import Path
from typing import Literal

from mementoagent.schema import AchievementItem, Evidence, RecordEnvelope
from mementoagent.validation import validate_record

RECORD_ID = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
CREATED_AT = "2025-01-12T09:30:00+08:00"
SOURCE_ID = "sha256:" + "a" * 64


def make_record(
    provenance: Literal["document", "user", "agent"] = "document",
    evidence: list[Evidence] | None = None,
) -> RecordEnvelope[AchievementItem]:
    """Build an achievement record for validation tests."""
    return RecordEnvelope[AchievementItem](
        id=RECORD_ID,
        schema="achievement/1",
        provenance=provenance,
        created_at=CREATED_AT,
        data=AchievementItem(
            kind="award",
            title="First Prize",
            organization="Competition Committee",
        ),
        evidence=evidence or [],
    )


def test_validate_record_accepts_document_evidence_without_page_or_quote(
    tmp_path: Path,
) -> None:
    """Accept source-level evidence when optional location fields are absent."""
    source_path = tmp_path / "sources" / "aa" / ("a" * 64 + ".pdf")
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"certificate")

    record = make_record(evidence=[Evidence(source=SOURCE_ID)])

    assert validate_record(tmp_path, record) == []


def test_validate_record_rejects_document_without_evidence(tmp_path: Path) -> None:
    """Require at least one evidence reference for document provenance."""
    record = make_record()

    assert validate_record(tmp_path, record) == [
        "document provenance requires at least one evidence item"
    ]


def test_validate_record_rejects_missing_source_reference(tmp_path: Path) -> None:
    """Report a source hash that has no stored source file."""
    record = make_record(evidence=[Evidence(source=SOURCE_ID, quote="First Prize")])

    assert validate_record(tmp_path, record) == [
        f"evidence source not found: {SOURCE_ID}"
    ]


def test_validate_record_allows_user_and_agent_records_without_evidence(
    tmp_path: Path,
) -> None:
    """Allow user and agent records to omit supporting source evidence."""
    for provenance in ("user", "agent"):
        assert validate_record(tmp_path, make_record(provenance)) == []


def test_validate_record_checks_sources_for_optional_evidence_on_user_record(
    tmp_path: Path,
) -> None:
    """Validate any source reference even when provenance is self-reported."""
    record = make_record("user", [Evidence(source=SOURCE_ID)])

    assert validate_record(tmp_path, record) == [
        f"evidence source not found: {SOURCE_ID}"
    ]
