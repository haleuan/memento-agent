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
        FileExistsError: If a `.memento` directory already exists at this location.
    """
    resolved_path = path.expanduser().resolve()
    memento_path = resolved_path / ".memento"
    if memento_path.exists():
        raise FileExistsError(f"Workspace already exists at {resolved_path}")

    memento_path.mkdir(parents=True, exist_ok=False)
    (memento_path / "parses").mkdir(parents=True, exist_ok=False)
    (memento_path / "cache").mkdir(parents=True, exist_ok=False)
    (memento_path / "workspace.toml").touch()

    for directory_name in ("inbox", "sources", "records", "outputs"):
        (resolved_path / directory_name).mkdir(parents=True, exist_ok=False)

    return resolved_path
