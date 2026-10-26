"""Canonical paths used by a Memento workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


def _extract_sha256_digest(value: str) -> str:
    """Extract the hexadecimal digest from a SHA-256 source reference.

    Args:
        value: SHA-256 reference, with or without its ``sha256:`` prefix.

    Returns:
        The 64-character lowercase digest.

    Raises:
        ValueError: If the reference is not a valid SHA-256 identifier.
    """
    _HASH_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")

    match = _HASH_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid source hash: {value!r}")
    return match.group(1)


@dataclass(frozen=True)
class WorkspacePaths:
    """Resolve canonical locations within one workspace root."""

    root: Path

    def __post_init__(self) -> None:
        """Expand and resolve the workspace root after initialization."""
        object.__setattr__(self, "root", self.root.expanduser().resolve())

    @property
    def inbox(self) -> Path:
        """Return the directory where new files are staged."""
        return self.root / "inbox"

    @property
    def sources(self) -> Path:
        """Return the directory containing immutable source files."""
        return self.root / "sources"

    @property
    def records(self) -> Path:
        """Return the directory containing memory records."""
        return self.root / "records"

    @property
    def outputs(self) -> Path:
        """Return the directory containing generated materials."""
        return self.root / "outputs"

    @property
    def memento(self) -> Path:
        """Return the workspace's internal state directory."""
        return self.root / ".memento"

    @property
    def workspace_config(self) -> Path:
        """Return the non-secret workspace TOML configuration path."""
        return self.memento / "workspace.toml"

    @property
    def parses(self) -> Path:
        """Return the directory containing immutable parse snapshots."""
        return self.memento / "parses"

    @property
    def ledger(self) -> Path:
        """Return the append-only audit ledger path."""
        return self.memento / "ledger.jsonl"

    @property
    def cache(self) -> Path:
        """Return the rebuildable cache directory."""
        return self.memento / "cache"

    def source_dir(self, source: str) -> Path:
        """Return the hash-prefix directory for a source.

        Args:
            source: SHA-256 source reference.

        Returns:
            Directory containing the source and its sidecar metadata.

        Raises:
            ValueError: If the source reference is malformed.
        """
        digest = _extract_sha256_digest(source)
        return self.sources / digest[:2]

    def source_candidates(self, source: str) -> list[Path]:
        """List source files matching a content hash.

        Args:
            source: SHA-256 source reference.

        Returns:
            Matching regular files, excluding JSON sidecars.

        Raises:
            ValueError: If the source reference is malformed.
        """
        digest = _extract_sha256_digest(source)
        directory = self.source_dir(digest)
        if not directory.is_dir():
            return []
        return sorted(
            path
            for path in directory.glob(f"{digest}.*")
            if path.is_file() and path.suffix != ".json"
        )

    def source_path(self, source: str) -> Path | None:
        """Return the first matching source file, if one exists.

        Args:
            source: SHA-256 source reference.

        Returns:
            First sorted match, or ``None`` when no source exists.
        """
        candidates = self.source_candidates(source)
        return candidates[0] if candidates else None

    def parse_dir(self, source: str, parse_id: str) -> Path:
        """Return a parse snapshot directory for a source and parse ID.

        Args:
            source: SHA-256 source reference.
            parse_id: Safe single-segment parse identifier.

        Returns:
            Directory for the referenced immutable parse snapshot.

        Raises:
            ValueError: If the source or parse identifier is unsafe.
        """
        digest = _extract_sha256_digest(source)
        if (
            not parse_id
            or parse_id in {".", ".."}
            or "/" in parse_id
            or "\\" in parse_id
            or Path(parse_id).is_absolute()
        ):
            raise ValueError("Invalid parse identifier")
        return self.parses / digest / parse_id

    def blocks_path(self, source: str, parse_id: str) -> Path:
        """Return the JSONL blocks path for a parse snapshot.

        Args:
            source: SHA-256 source reference.
            parse_id: Safe parse snapshot identifier.
        """
        return self.parse_dir(source, parse_id) / "blocks.jsonl"

    def parse_meta_path(self, source: str, parse_id: str) -> Path:
        """Return the metadata path for a parse snapshot.

        Args:
            source: SHA-256 source reference.
            parse_id: Safe parse snapshot identifier.
        """
        return self.parse_dir(source, parse_id) / "meta.json"
