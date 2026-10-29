"""Workspace discovery and evidence paths."""

from dataclasses import dataclass
from pathlib import Path
import re


class WorkspaceNotFoundError(FileNotFoundError):
    """Raised when no ancestor contains a `.memento` directory."""


def find_workspace(start: Path | str) -> Path:
    """Walk upward from a path and return the nearest workspace root.

    Args:
        start: File or directory from which to begin the upward search.

    Returns:
        The nearest ancestor containing a `.memento` directory.

    Raises:
        WorkspaceNotFoundError: If no ancestor is a Memento workspace.
    """
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
    def _extract_hex_digest(hash_identifier: str) -> str:
        """Return the digest from a source identifier.

        Args:
            hash_identifier: Source identifier in `sha256:<64 lowercase hex digits>` form.

        Returns:
            The hexadecimal digest without its `sha256:` prefix.

        Raises:
            ValueError: If the source identifier has an invalid format.
        """
        match = re.fullmatch(r"sha256:([0-9a-f]{64})", hash_identifier)
        if not match:
            raise ValueError("invalid source hash")
        return match.group(1)

    def find_source_file_by_hash(self, hash_file_identifier: str) -> Path | None:
        """Return the first source file matching a content hash.

        Args:
            hash_file_identifier: Source identifier whose stored file should be located.

        Returns:
            The first matching source file, or `None` when no file exists.

        Raises:
            ValueError: If the source identifier has an invalid format.
        """
        digest = self._extract_hex_digest(hash_file_identifier)
        directory = self.root / "sources" / digest[:2]

        # TODO (TD-001): Consider it's not `.json` files friendly to ignore them here, but they are not the source files themselves.
        matches = sorted(
            path
            for path in (directory / digest, *directory.glob(f"{digest}.*"))
            if path.is_file() and path.suffix != ".json"
        )
        return matches[0] if matches else None

    def parse_snapshot_dir(self, source: str, parse_id: str) -> Path:
        """Return a parse snapshot directory after path validation.

        Args:
            source: Source identifier for the parse snapshot.
            parse_id: Identifier of the parse snapshot.

        Returns:
            Path to the snapshot directory.

        Raises:
            ValueError: If either identifier has an invalid format.
        """
        digest = self._extract_hex_digest(source)
        if not re.fullmatch(r"parse_[0-9a-f]{32}", parse_id):
            raise ValueError("invalid parse identifier")
        return self.root / ".memento" / "parses" / digest / parse_id
