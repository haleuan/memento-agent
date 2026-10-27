"""Workspace discovery and evidence paths."""

from dataclasses import dataclass
from pathlib import Path
import re


class WorkspaceNotFoundError(FileNotFoundError):
    """Raised when no ancestor contains a `.memento` directory."""


def find_workspace(start: Path | str) -> Path:
    """Walk upward from a path and return the nearest workspace root."""
    path = Path(start).expanduser().resolve()
    if path.is_file():
        path = path.parent
    for candidate in (path, *path.parents):
        if (candidate / ".memento").is_dir():
            return candidate
    raise WorkspaceNotFoundError("Not in a memento workspace (no .memento/ found)")


@dataclass(frozen=True)
class WorkspacePaths:
    """Resolve source and parse paths inside a workspace."""

    root: Path

    def __post_init__(self) -> None:
        """Resolve the workspace root."""
        object.__setattr__(self, "root", self.root.expanduser().resolve())

    @staticmethod
    def _digest(source: str) -> str:
        """Return the digest from a source identifier."""
        match = re.fullmatch(r"sha256:([0-9a-f]{64})", source)
        if not match:
            raise ValueError("invalid source hash")
        return match.group(1)

    def source_path(self, source: str) -> Path | None:
        """Return the first source file matching a content hash."""
        digest = self._digest(source)
        directory = self.root / "sources" / digest[:2]
        matches = sorted(
            path for path in directory.glob(f"{digest}.*")
            if path.is_file() and path.suffix != ".json"
        )
        return matches[0] if matches else None

    def blocks_path(self, source: str, parse_id: str) -> Path:
        """Return a parse snapshot's block file after path validation."""
        digest = self._digest(source)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", parse_id):
            raise ValueError("invalid parse identifier")
        return self.root / ".memento" / "parses" / digest / parse_id / "blocks.jsonl"
