"""Tests for the read-only record validation command."""

from pathlib import Path
from typing import Literal

import pytest

from mementoagent.cli import main
from mementoagent.schema import AchievementItem, Evidence, RecordEnvelope
from mementoagent.workspace import import_source, init_workspace, save_record


RECORD_ID = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
CREATED_AT = "2025-01-12T09:30:00+08:00"
SOURCE_ID = "sha256:" + "a" * 64


def make_record(
    provenance: Literal["document", "user", "agent"] = "document",
    evidence: list[Evidence] | None = None,
) -> RecordEnvelope[AchievementItem]:
    """Build an achievement record for CLI tests."""
    return RecordEnvelope[AchievementItem](
        id=RECORD_ID,
        schema="achievement/1",
        provenance=provenance,
        created_at=CREATED_AT,
        data=AchievementItem(
            kind="certificate",
            title="Certificate of Completion",
            organization="Memento Institute",
        ),
        evidence=evidence or [],
    )


def test_main_check_accepts_valid_record_with_relative_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Validate a record and discover its workspace from a relative path."""
    workspace_root = init_workspace(tmp_path / "workspace")
    source_path = tmp_path / "certificate.pdf"
    source_path.write_bytes(b"certificate")
    source_id = import_source(workspace_root, source_path)
    record_path = save_record(
        workspace_root,
        make_record(evidence=[Evidence(source=source_id)]),
    )
    monkeypatch.chdir(workspace_root)

    result = main(["check", str(record_path.relative_to(workspace_root))])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == "OK\n"
    assert captured.err == ""


def test_main_check_reports_missing_document_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return a failure when a document record has no evidence."""
    workspace_root = init_workspace(tmp_path / "workspace")
    record_path = save_record(workspace_root, make_record())

    result = main(["check", str(record_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert (
        "error: document provenance requires at least one evidence item" in captured.err
    )


def test_main_check_reports_missing_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return a failure when evidence points to an absent source file."""
    workspace_root = init_workspace(tmp_path / "workspace")
    record_path = save_record(
        workspace_root,
        make_record(evidence=[Evidence(source=SOURCE_ID)]),
    )

    result = main(["check", str(record_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert f"error: evidence source not found: {SOURCE_ID}" in captured.err


def test_main_check_reports_missing_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return a failure when the requested record file does not exist."""
    workspace_root = init_workspace(tmp_path / "workspace")
    record_path = workspace_root / "records" / "achievement" / "missing.toml"

    result = main(["check", str(record_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")


@pytest.mark.parametrize(
    "content",
    [
        "id = [",
        'id = "invalid"\n',
    ],
)
def test_main_check_reports_invalid_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    content: str,
) -> None:
    """Return a failure when TOML or record validation fails."""
    workspace_root = init_workspace(tmp_path / "workspace")
    record_path = workspace_root / "records" / "achievement" / "invalid.toml"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(content, encoding="utf-8")

    result = main(["check", str(record_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")


def test_main_check_reports_record_outside_workspace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return a failure when no workspace ancestor exists."""
    record_path = tmp_path / "record.toml"

    result = main(["check", str(record_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert captured.err.startswith("error: ")


@pytest.mark.parametrize("argv", [["check"], ["unknown", "record.toml"]])
def test_main_rejects_invalid_arguments(argv: list[str]) -> None:
    """Use argparse's standard exit code for invalid command arguments."""
    with pytest.raises(SystemExit) as error:
        main(argv)

    assert error.value.code == 2
