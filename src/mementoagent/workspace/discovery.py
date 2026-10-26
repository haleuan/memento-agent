"""Locate a Memento workspace by its ``.memento`` marker."""

from __future__ import annotations

from pathlib import Path

_cache: dict[Path, Path] = {}


class WorkspaceNotFoundError(FileNotFoundError):
    """Raised when no ancestor contains a Memento marker directory."""


def clear_workspace_cache() -> None:
    """Clear cached workspace discoveries."""
    _cache.clear()


def find_workspace(start: Path | str | None = None) -> Path:
    """Return the nearest workspace root at or above *start*.

    `start` may be a directory or a path to a file. The returned path is
    absolute and resolved, making it safe to use for portable relative paths.

    Args:
        start: Directory or file path from which to search; defaults to cwd.

    Returns:
        The nearest ancestor containing a `.memento` directory.

    Raises:
        WorkspaceNotFoundError: If no ancestor contains a workspace marker.
    """
    candidate = Path.cwd() if start is None else Path(start)
    candidate = candidate.expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent
    key = candidate
    cached = _cache.get(key)
    if cached is not None:
        return cached
    for current in (candidate, *candidate.parents):
        marker = current / ".memento"
        if marker.is_dir():
            _cache[key] = current
            return current
    raise WorkspaceNotFoundError("Not in a memento workspace (no .memento/ found)")
