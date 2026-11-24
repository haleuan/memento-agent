"""Tests for importing files into content-addressed source storage."""

import hashlib
from pathlib import Path

import pytest

from mementoagent.workspace import import_source


def test_import_source_moves_file_to_content_addressed_path(tmp_path: Path) -> None:
    """Hash and move a source file below its digest prefix directory."""
    content = b"certificate\x00data"
    source_file = tmp_path / "inbox" / "certificate.pdf"
    source_file.parent.mkdir()
    source_file.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()

    source_id = import_source(tmp_path, source_file)

    destination = tmp_path / "sources" / digest[:2] / f"{digest}.pdf"
    assert source_id == f"sha256:{digest}"
    assert not source_file.exists()
    assert destination.read_bytes() == content


def test_import_source_stores_extensionless_file_without_suffix(
    tmp_path: Path,
) -> None:
    """Store a source with no extension under a hash-only filename."""
    content = b"plain source"
    source_file = tmp_path / "inbox" / "certificate"
    source_file.parent.mkdir()
    source_file.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()

    import_source(tmp_path, source_file)

    destination = tmp_path / "sources" / digest[:2] / digest
    assert destination.read_bytes() == content
    assert not source_file.exists()


def test_import_source_is_idempotent_when_destination_exists(
    tmp_path: Path,
) -> None:
    """Reuse an existing content-addressed file without overwriting it."""
    content = b"same source"
    source_file = tmp_path / "inbox" / "first.pdf"
    source_file.parent.mkdir()
    source_file.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    destination = tmp_path / "sources" / digest[:2] / f"{digest}.pdf"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing content")

    source_id = import_source(tmp_path, source_file)

    assert source_id == f"sha256:{digest}"
    assert source_file.read_bytes() == content
    assert destination.read_bytes() == b"existing content"


def test_import_source_rejects_relative_workspace_root(tmp_path: Path) -> None:
    """Require an absolute workspace root before importing a source."""
    source_file = tmp_path / "source.pdf"
    source_file.write_bytes(b"source")

    with pytest.raises(ValueError, match="workspace_root must be absolute"):
        import_source(Path("workspace"), source_file)


def test_import_source_rejects_missing_file(tmp_path: Path) -> None:
    """Raise FileNotFoundError when the source path does not exist."""
    with pytest.raises(FileNotFoundError):
        import_source(tmp_path, tmp_path / "missing.pdf")


def test_import_source_rejects_directory_path(tmp_path: Path) -> None:
    """Raise FileNotFoundError when the source path is a directory."""
    source_directory = tmp_path / "inbox"
    source_directory.mkdir()

    with pytest.raises(FileNotFoundError):
        import_source(tmp_path, source_directory)
