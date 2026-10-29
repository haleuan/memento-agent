"""Tests for structured TOML record file I/O."""

from pathlib import Path
import tomllib

import pytest
from pydantic import ValidationError

from mementoagent.schema import AchievementItem, Evidence, RecordEnvelope
from mementoagent.schema.envelope import TimeRange
from mementoagent.schema.types import PartialDate
from mementoagent.workspace import load_record, save_record


VALID_RECORD_ID = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
VALID_HASH = "sha256:" + "a" * 64
CREATED_AT = "2025-01-12T09:30:00+08:00"


def make_record() -> RecordEnvelope[AchievementItem]:
    """Build a complete achievement record for file I/O tests."""
    return RecordEnvelope[AchievementItem](
        id=VALID_RECORD_ID,
        schema="achievement/1",
        provenance="document",
        created_at=CREATED_AT,
        occurred=TimeRange(start=PartialDate(year=2024, month=10, precision="month")),
        data=AchievementItem(
            kind="award",
            title="National Mathematical Modeling Contest",
            organization="Competition Committee",
            level_raw="First Prize",
            certificate_number="CERT-123",
        ),
        evidence=[Evidence(source=VALID_HASH, page=1, quote="First Prize")],
    )


def test_save_record_writes_toml_document(tmp_path: Path) -> None:
    """Write a structured record without front matter delimiters or nulls."""
    record = make_record()

    path = save_record(tmp_path, record)

    assert path == tmp_path / "records" / "achievement" / f"{record.id}.toml"
    content = path.read_text(encoding="utf-8")
    assert "---" not in content
    with path.open("rb") as record_file:
        data = tomllib.load(record_file)
    assert data["schema"] == "achievement/1"
    assert data["created_at"] == CREATED_AT
    assert data["data"]["title"] == record.data.title
    assert data["data"]["certificate_number"] == "CERT-123"
    assert "body" not in data
    assert "end" not in data["occurred"]
    assert "description" not in data["data"]


def test_load_record_round_trips_structured_record(tmp_path: Path) -> None:
    """Load a saved TOML record without changing its structured data."""
    record = make_record()
    path = save_record(tmp_path, record)

    loaded = load_record(path, AchievementItem)

    assert loaded == record


def test_record_rejects_legacy_body_field() -> None:
    """Reject the removed free-form body field from the record contract."""
    with pytest.raises(ValidationError):
        RecordEnvelope[AchievementItem].model_validate(
            {
                "id": VALID_RECORD_ID,
                "schema": "achievement/1",
                "provenance": "user",
                "created_at": CREATED_AT,
                "data": {
                    "kind": "award",
                    "title": "First Prize",
                    "organization": "Competition Committee",
                },
                "body": "legacy markdown",
            }
        )


def test_save_record_rejects_relative_workspace_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject a workspace root whose meaning depends on the current directory."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="workspace_root must be absolute"):
        save_record(Path("workspace"), make_record())


def test_load_record_raises_for_missing_file(tmp_path: Path) -> None:
    """Raise FileNotFoundError when the record path does not exist."""
    with pytest.raises(FileNotFoundError):
        load_record(tmp_path / "missing.toml", AchievementItem)


def test_load_record_rejects_invalid_toml(tmp_path: Path) -> None:
    """Reject malformed TOML before validating the record schema."""
    path = tmp_path / "invalid.toml"
    path.write_text("id = [", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid TOML record"):
        load_record(path, AchievementItem)


def test_load_record_rejects_invalid_record_data(tmp_path: Path) -> None:
    """Reject TOML that parses but violates the record schema."""
    path = tmp_path / "invalid-record.toml"
    path.write_text(
        'id = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"\n'
        'schema = "achievement/1"\n'
        'provenance = "document"\n'
        f'created_at = "{CREATED_AT}"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid record"):
        load_record(path, AchievementItem)
