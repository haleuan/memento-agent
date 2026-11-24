"""Tests for parse snapshot persistence."""

import re
import tomllib
from pathlib import Path

import pytest

from mementoagent.schema import ParseSnapshot
from mementoagent.workspace import (
    WorkspacePaths,
    import_source,
    init_workspace,
    load_parse_snapshot,
    save_parse_snapshot,
)


def import_certificate(workspace_root: Path, tmp_path: Path) -> str:
    """Import binary certificate data and return its source identifier."""
    source_path = tmp_path / "certificate.pdf"
    source_path.write_bytes(b"certificate")
    return import_source(workspace_root, source_path)


def test_save_parse_snapshot_persists_metadata_and_exact_content(
    tmp_path: Path,
) -> None:
    """Save a snapshot with generated ID and preserve its complete Markdown."""
    workspace_root = init_workspace(tmp_path / "workspace")
    source_id = import_certificate(workspace_root, tmp_path)
    content = "# 奖状\n\n---\n获奖者：林\n"

    snapshot_dir = save_parse_snapshot(
        workspace_root,
        source_id,
        "example-parser",
        "1.2.3",
        content,
    )

    digest = source_id.removeprefix("sha256:")
    assert snapshot_dir.parent == workspace_root / ".memento" / "parses" / digest
    assert re.fullmatch(r"parse_[0-9a-f]{32}", snapshot_dir.name)
    assert (snapshot_dir / "metadata.toml").is_file()
    assert (snapshot_dir / "content.md").read_text(encoding="utf-8") == content
    with (snapshot_dir / "metadata.toml").open("rb") as metadata_file:
        metadata = tomllib.load(metadata_file)
    assert metadata["schema"] == "parse/1"
    assert metadata["parse_id"] == snapshot_dir.name
    assert metadata["source"] == source_id
    assert metadata["parser"] == "example-parser"
    assert metadata["parser_version"] == "1.2.3"
    assert metadata["created_at"]
    assert not (snapshot_dir / "blocks.jsonl").exists()

    assert load_parse_snapshot(snapshot_dir) == ParseSnapshot(
        metadata=metadata,
        content=content,
    )


def test_save_parse_snapshot_creates_new_directory_each_time(
    tmp_path: Path,
) -> None:
    """Save repeated parses as separate snapshots without replacing the first."""
    workspace_root = init_workspace(tmp_path / "workspace")
    source_id = import_certificate(workspace_root, tmp_path)

    first = save_parse_snapshot(workspace_root, source_id, "parser", "1", "first")
    second = save_parse_snapshot(workspace_root, source_id, "parser", "1", "second")

    assert first != second
    assert load_parse_snapshot(first).content == "first"
    assert load_parse_snapshot(second).content == "second"


def test_save_parse_snapshot_rejects_missing_source(tmp_path: Path) -> None:
    """Require the referenced source to exist in workspace storage."""
    workspace_root = init_workspace(tmp_path / "workspace")

    with pytest.raises(FileNotFoundError):
        save_parse_snapshot(
            workspace_root,
            "sha256:" + "a" * 64,
            "parser",
            "1",
            "content",
        )


@pytest.mark.parametrize("filename", ["metadata.toml", "content.md"])
def test_load_parse_snapshot_rejects_missing_file(
    tmp_path: Path,
    filename: str,
) -> None:
    """Raise FileNotFoundError when either required snapshot file is absent."""
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    if filename == "metadata.toml":
        (snapshot_dir / "content.md").write_text("content", encoding="utf-8")
    else:
        (snapshot_dir / "metadata.toml").write_text(
            'schema = "parse/1"\n',
            encoding="utf-8",
        )

    with pytest.raises(FileNotFoundError):
        load_parse_snapshot(snapshot_dir)


def test_load_parse_snapshot_rejects_invalid_toml(tmp_path: Path) -> None:
    """Reject malformed TOML metadata."""
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "metadata.toml").write_text("schema = [", encoding="utf-8")
    (snapshot_dir / "content.md").write_text("content", encoding="utf-8")

    with pytest.raises(ValueError):
        load_parse_snapshot(snapshot_dir)


def test_load_parse_snapshot_rejects_invalid_metadata(tmp_path: Path) -> None:
    """Reject TOML metadata that does not satisfy the schema."""
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "metadata.toml").write_text(
        'schema = "parse/1"\nparse_id = "invalid"\n',
        encoding="utf-8",
    )
    (snapshot_dir / "content.md").write_text("content", encoding="utf-8")

    with pytest.raises(ValueError):
        load_parse_snapshot(snapshot_dir)


def test_load_parse_snapshot_rejects_metadata_without_schema(
    tmp_path: Path,
) -> None:
    """Reject metadata without an explicit schema version."""
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "metadata.toml").write_text(
        'parse_id = "parse_' + "a" * 32 + '"\n'
        'source = "sha256:' + "b" * 64 + '"\n'
        'parser = "example-parser"\n'
        'parser_version = "1.0.0"\n'
        'created_at = "2025-01-12T09:30:00+08:00"\n',
        encoding="utf-8",
    )
    (snapshot_dir / "content.md").write_text("content", encoding="utf-8")

    with pytest.raises(ValueError):
        load_parse_snapshot(snapshot_dir)


def test_load_parse_snapshot_rejects_parse_id_directory_mismatch(
    tmp_path: Path,
) -> None:
    """Require the metadata parse ID to match its snapshot directory."""
    snapshot_dir = tmp_path / "parses" / ("a" * 64) / ("parse_" + "b" * 32)
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "metadata.toml").write_text(
        'schema = "parse/1"\n'
        'parse_id = "parse_' + "c" * 32 + '"\n'
        'source = "sha256:' + "a" * 64 + '"\n'
        'parser = "example-parser"\n'
        'parser_version = "1.0.0"\n'
        'created_at = "2025-01-12T09:30:00+08:00"\n',
        encoding="utf-8",
    )
    (snapshot_dir / "content.md").write_text("content", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="parse ID does not match snapshot directory name",
    ):
        load_parse_snapshot(snapshot_dir)


def test_load_parse_snapshot_rejects_source_digest_directory_mismatch(
    tmp_path: Path,
) -> None:
    """Require the metadata source digest to match its parent directory."""
    source_digest = "a" * 64
    parent_digest = "b" * 64
    parse_id = "parse_" + "c" * 32
    snapshot_dir = tmp_path / "parses" / parent_digest / parse_id
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "metadata.toml").write_text(
        'schema = "parse/1"\n'
        f'parse_id = "{parse_id}"\n'
        f'source = "sha256:{source_digest}"\n'
        'parser = "example-parser"\n'
        'parser_version = "1.0.0"\n'
        'created_at = "2025-01-12T09:30:00+08:00"\n',
        encoding="utf-8",
    )
    (snapshot_dir / "content.md").write_text("content", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="source digest does not match snapshot directory parent",
    ):
        load_parse_snapshot(snapshot_dir)


def test_workspace_paths_builds_parse_snapshot_directory(tmp_path: Path) -> None:
    """Resolve snapshot paths using the source digest and parse identifier."""
    source_id = "sha256:" + "c" * 64
    parse_id = "parse_" + "d" * 32

    result = WorkspacePaths(tmp_path).parse_snapshot_dir(source_id, parse_id)

    assert result == tmp_path / ".memento" / "parses" / ("c" * 64) / parse_id
