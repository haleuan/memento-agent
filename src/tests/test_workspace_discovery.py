"""Tests for workspace discovery and content-addressed path resolution."""

from pathlib import Path

import pytest

from mementoagent.workspace import (
    WorkspaceNotFoundError,
    WorkspacePaths,
    find_workspace,
)


VALID_DIGEST = "ab" * 32
VALID_HASH = f"sha256:{VALID_DIGEST}"


def test_find_workspace_returns_workspace_for_current_directory(tmp_path: Path) -> None:
    """Find a workspace marker located directly in the starting directory."""
    (tmp_path / ".memento").mkdir()

    assert find_workspace(tmp_path) == tmp_path


def test_find_workspace_walks_up_to_parent_directory(tmp_path: Path) -> None:
    """Walk through ancestors until the nearest workspace marker is found."""
    nested = tmp_path / "records" / "achievement"
    nested.mkdir(parents=True)
    (tmp_path / ".memento").mkdir()

    assert find_workspace(nested) == tmp_path


def test_find_workspace_resolves_from_file_path(tmp_path: Path) -> None:
    """Treat a file start path as a request to search from its parent."""
    (tmp_path / ".memento").mkdir()
    source_file = tmp_path / "records" / "record.toml"
    source_file.parent.mkdir()
    source_file.write_text("", encoding="utf-8")

    assert find_workspace(source_file) == tmp_path


def test_find_workspace_raises_when_no_workspace_exists(tmp_path: Path) -> None:
    """Raise WorkspaceNotFoundError when no ancestor has a marker directory."""
    with pytest.raises(WorkspaceNotFoundError):
        find_workspace(tmp_path)


def test_workspace_paths_finds_source_file_by_hash(tmp_path: Path) -> None:
    """Return the content-addressed source file while ignoring parse metadata."""
    source_directory = tmp_path / "sources" / VALID_DIGEST[:2]
    source_directory.mkdir(parents=True)
    source_file = source_directory / f"{VALID_DIGEST}.pdf"
    source_file.write_bytes(b"certificate")
    (source_directory / f"{VALID_DIGEST}.json").write_text("{}", encoding="utf-8")

    assert WorkspacePaths(tmp_path).find_source_file_by_hash(VALID_HASH) == source_file


def test_workspace_paths_returns_none_for_missing_source_file(tmp_path: Path) -> None:
    """Return None when no stored source file matches the requested hash."""
    assert WorkspacePaths(tmp_path).find_source_file_by_hash(VALID_HASH) is None


@pytest.mark.parametrize(
    "hash_identifier",
    ["sha256:", "sha256:" + "A" * 64, "sha256:" + "a" * 63, "md5:" + "a" * 64],
)
def test_workspace_paths_rejects_invalid_source_hash(
    hash_identifier: str, tmp_path: Path
) -> None:
    """Reject source identifiers that are not lowercase SHA-256 hashes."""
    with pytest.raises(ValueError, match="invalid source hash"):
        WorkspacePaths(tmp_path).find_source_file_by_hash(hash_identifier)


def test_workspace_paths_builds_blocks_path(tmp_path: Path) -> None:
    """Build the validated path for a parse snapshot block file."""
    result = WorkspacePaths(tmp_path).blocks_path(VALID_HASH, "parse_01")

    assert (
        result
        == tmp_path / ".memento" / "parses" / VALID_DIGEST / "parse_01" / "blocks.jsonl"
    )


def test_workspace_paths_blocks_path_rejects_invalid_hash(tmp_path: Path) -> None:
    """Reject an invalid source hash before constructing a blocks path."""
    with pytest.raises(ValueError, match="invalid source hash"):
        WorkspacePaths(tmp_path).blocks_path("sha256:bad", "parse_01")


@pytest.mark.parametrize("parse_id", ["", "bad/id", "bad id"])
def test_workspace_paths_blocks_path_rejects_invalid_parse_id(
    parse_id: str, tmp_path: Path
) -> None:
    """Reject parse identifiers that could escape the snapshot directory."""
    with pytest.raises(ValueError, match="invalid parse identifier"):
        WorkspacePaths(tmp_path).blocks_path(VALID_HASH, parse_id)
