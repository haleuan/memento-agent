"""Tests for YAML front matter and Markdown record file I/O."""

from pathlib import Path

import pytest
import yaml

from mementoagent.schema import AchievementItem, Evidence, RecordEnvelope
from mementoagent.schema.envelope import TimeRange
from mementoagent.schema.types import PartialDate
from mementoagent.workspace import load_record, save_record


VALID_RECORD_ID = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
VALID_HASH = "sha256:" + "a" * 64
CREATED_AT = "2025-01-12T09:30:00+08:00"


def make_record(body: str = "") -> RecordEnvelope[AchievementItem]:
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
        ),
        evidence=[Evidence(source=VALID_HASH, page=1, quote="First Prize")],
        body=body,
    )


def test_save_record_writes_yaml_front_matter_and_body(tmp_path: Path) -> None:
    """Write the record to its schema directory with YAML and Markdown sections."""
    record = make_record("Personal reflection.")

    path = save_record(tmp_path, record)

    assert path == tmp_path / "records" / "achievement" / f"{record.id}.yaml"
    content = path.read_text(encoding="utf-8")
    sections = content.split("---\n", 2)
    assert sections[0] == ""
    assert sections[2] == "\nPersonal reflection."

    front_matter = yaml.safe_load(sections[1])
    assert front_matter["schema"] == "achievement/1"
    assert front_matter["created_at"] == CREATED_AT
    assert front_matter["data"]["title"] == record.data.title


def test_load_record_round_trips_record_with_body(tmp_path: Path) -> None:
    """Load a saved record with Markdown body without changing its data."""
    record = make_record("Personal reflection.")
    path = save_record(tmp_path, record)

    loaded = load_record(path, AchievementItem)

    assert loaded == record


def test_load_record_round_trips_record_with_empty_body(tmp_path: Path) -> None:
    """Load a saved record whose Markdown body is empty."""
    record = make_record()
    path = save_record(tmp_path, record)

    loaded = load_record(path, AchievementItem)

    assert loaded == record
    assert loaded.body == ""


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
        load_record(tmp_path / "missing.yaml", AchievementItem)


def test_load_record_rejects_invalid_yaml_front_matter(tmp_path: Path) -> None:
    """Reject malformed YAML before validating the record schema."""
    path = tmp_path / "invalid.yaml"
    path.write_text("---\n[unclosed\n---\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid YAML front matter"):
        load_record(path, AchievementItem)


def test_load_record_rejects_non_mapping_front_matter(tmp_path: Path) -> None:
    """Reject YAML front matter that is not a mapping."""
    path = tmp_path / "list.yaml"
    path.write_text("---\n- item\n---\n", encoding="utf-8")

    with pytest.raises(ValueError, match="YAML front matter must be a mapping"):
        load_record(path, AchievementItem)


def test_load_record_rejects_invalid_record_data(tmp_path: Path) -> None:
    """Reject front matter that parses as YAML but violates the record schema."""
    path = tmp_path / "invalid-record.yaml"
    path.write_text(
        "---\n"
        "id: ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF\n"
        "schema: achievement/1\n"
        "provenance: document\n"
        f'created_at: "{CREATED_AT}"\n'
        "---\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid record"):
        load_record(path, AchievementItem)
