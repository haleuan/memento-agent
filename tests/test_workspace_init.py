"""Tests for creating new Memento workspaces."""

from pathlib import Path

import pytest

from mementoagent.workspace import init_workspace


def test_init_workspace_creates_standard_structure(tmp_path: Path) -> None:
    """Create all workspace directories and an empty workspace metadata file."""
    root = init_workspace(tmp_path / "vault")

    for directory_name in (
        ".memento",
        "inbox",
        "sources",
        "records",
        "outputs",
    ):
        assert (root / directory_name).is_dir()
    assert (root / ".memento" / "parses").is_dir()
    assert (root / ".memento" / "cache").is_dir()
    workspace_file = root / ".memento" / "workspace.toml"
    assert workspace_file.is_file()
    assert workspace_file.read_bytes() == b""


def test_init_workspace_returns_absolute_path(tmp_path: Path) -> None:
    """Return the resolved absolute workspace root."""
    root = init_workspace(tmp_path / "vault")

    assert root.is_absolute()
    assert root == (tmp_path / "vault").resolve()


def test_init_workspace_resolves_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolve relative workspace paths from the current working directory."""
    monkeypatch.chdir(tmp_path)

    root = init_workspace(Path("nested"))

    assert root == (tmp_path / "nested").resolve()


def test_init_workspace_expands_home_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expand a tilde using the configured home directory."""
    monkeypatch.setenv("HOME", str(tmp_path))

    root = init_workspace(Path("~/vault"))

    assert root == (tmp_path / "vault").resolve()


def test_init_workspace_creates_missing_parent_directories(tmp_path: Path) -> None:
    """Create intermediate parent directories for a nested workspace path."""
    target = tmp_path / "missing" / "parents" / "vault"

    root = init_workspace(target)

    assert root == target.resolve()
    assert root.is_dir()


def test_init_workspace_rejects_existing_memento_directory(tmp_path: Path) -> None:
    """Raise FileExistsError when the target already has a .memento entry."""
    target = tmp_path / "vault"
    (target / ".memento").mkdir(parents=True)

    with pytest.raises(FileExistsError) as error:
        init_workspace(target)

    assert str(error.value) == f"Workspace already exists at {target.resolve()}"


@pytest.mark.parametrize("name", ["inbox", "sources", "records", "outputs"])
@pytest.mark.parametrize("entry_type", ["directory", "file"])
def test_init_workspace_rejects_conflicts_before_creating_paths(
    tmp_path: Path, name: str, entry_type: str
) -> None:
    """Leave existing contents unchanged and allow retry after removing a conflict."""
    target = tmp_path / "workspace"
    target.mkdir()
    conflict = target / name
    if entry_type == "directory":
        conflict.mkdir()
        original = conflict / "original.txt"
    else:
        original = conflict
    original.write_text("preserve me", encoding="utf-8")

    with pytest.raises(FileExistsError):
        init_workspace(target)

    assert original.read_text(encoding="utf-8") == "preserve me"
    assert list(target.iterdir()) == [conflict]
    assert not (target / ".memento").exists()

    original.unlink()
    if entry_type == "directory":
        conflict.rmdir()

    assert init_workspace(target) == target.resolve()


def test_init_workspace_rejects_broken_marker_symlink(tmp_path: Path) -> None:
    """Treat an existing marker entry as a conflict even if its target is absent."""
    marker = tmp_path / ".memento"
    marker.symlink_to(tmp_path / "missing-marker")

    with pytest.raises(FileExistsError):
        init_workspace(tmp_path)

    assert list(tmp_path.iterdir()) == [marker]
