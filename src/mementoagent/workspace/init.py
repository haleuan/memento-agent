"""Workspace initialization."""

from pathlib import Path


def init_workspace(path: Path) -> Path:
    """Initialize a new Memento workspace at the given path.

    Creates the standard directory structure for a Memento workspace.

    Args:
        path: Directory where the workspace will be created.
            Can be relative or absolute; will be resolved.

    Returns:
        Absolute path to the workspace root.

    Raises:
        FileExistsError: If `.memento` or a standard workspace path already exists.
    """
    resolved_path = path.expanduser().resolve()
    memento_path = resolved_path / ".memento"
    if memento_path.exists() or memento_path.is_symlink():
        raise FileExistsError(f"Workspace already exists at {resolved_path}")

    directory_paths = [
        resolved_path / name for name in ("inbox", "sources", "records", "outputs")
    ]
    for directory in directory_paths:
        if directory.exists() or directory.is_symlink():
            raise FileExistsError(f"Workspace path already exists: {directory}")

    for directory in directory_paths:
        directory.mkdir(parents=True, exist_ok=False)

    memento_path.mkdir(parents=True, exist_ok=False)
    (memento_path / "parses").mkdir(parents=True, exist_ok=False)
    (memento_path / "cache").mkdir(parents=True, exist_ok=False)
    (memento_path / "workspace.toml").touch()

    return resolved_path
