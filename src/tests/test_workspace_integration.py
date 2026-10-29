"""Tests for the end-to-end workspace record flow."""

from pathlib import Path

from mementoagent.schema import AchievementItem, Evidence, RecordEnvelope
from mementoagent.workspace import (
    import_source,
    init_workspace,
    load_record,
    save_record,
)


RECORD_ID = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
CREATED_AT = "2025-01-12T09:30:00+08:00"


def test_workspace_source_and_record_flow_round_trips(
    tmp_path: Path,
) -> None:
    """Import a source and persist a record that references it."""
    workspace_root = init_workspace(tmp_path / "workspace")
    source_path = tmp_path / "certificate.pdf"
    source_path.write_bytes(b"certificate evidence")

    source_identifier = import_source(workspace_root, source_path)
    digest = source_identifier.removeprefix("sha256:")
    stored_source = workspace_root / "sources" / digest[:2] / f"{digest}.pdf"

    record = RecordEnvelope[AchievementItem](
        id=RECORD_ID,
        schema="achievement/1",
        provenance="document",
        created_at=CREATED_AT,
        data=AchievementItem(
            kind="certificate",
            title="Certificate of Completion",
            organization="Memento Institute",
            certificate_number="CERT-123",
        ),
        evidence=[
            Evidence(
                source=source_identifier,
                page=1,
                quote="Certificate of Completion",
                supports=["data.title"],
            )
        ],
    )

    record_path = save_record(workspace_root, record)
    loaded_record = load_record(record_path, AchievementItem)

    assert stored_source.is_file()
    assert not source_path.exists()
    assert record_path == (
        workspace_root / "records" / "achievement" / f"{RECORD_ID}.toml"
    )
    assert loaded_record == record
