"""Persist successful parse snapshots in a workspace."""

from datetime import datetime
from pathlib import Path
import tomllib
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
import tomli_w

from mementoagent.schema import ParseSnapshot, ParseSnapshotMetadata

from .discovery import WorkspacePaths


def save_parse_snapshot(
    workspace_root: Path,
    source: str,
    parser: str,
    parser_version: str,
    content: str,
) -> Path:
    """Save successful parser output and metadata to the workspace.

    Args:
        workspace_root: Absolute path to the workspace root.
        source: Hash identifier of an imported source file.
        parser: Name of the parser that produced the content.
        parser_version: Version of the parser that produced the content.
        content: Complete Markdown output from the parser.

    Returns:
        The directory containing `metadata.toml` and `content.md`.

    Raises:
        ValueError: If `workspace_root` is not absolute or `source` is invalid.
        FileNotFoundError: If the referenced source file is not in the workspace.
    """
    if not workspace_root.is_absolute():
        raise ValueError("workspace_root must be absolute")

    paths = WorkspacePaths(workspace_root)
    if paths.find_source_file_by_hash(source) is None:
        raise FileNotFoundError(f"source file not found: {source}")

    parse_id = f"parse_{uuid4().hex}"
    metadata = ParseSnapshotMetadata(
        schema="parse/1",
        parse_id=parse_id,
        source=source,
        parser=parser,
        parser_version=parser_version,
        created_at=datetime.now().astimezone().isoformat(),
    )
    serialized_metadata = tomli_w.dumps(
        metadata.model_dump(by_alias=True, mode="json"),
    )
    snapshot_dir = paths.parse_snapshot_dir(source, parse_id)
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    with (snapshot_dir / "metadata.toml").open(
        "w", encoding="utf-8", newline=""
    ) as metadata_file:
        metadata_file.write(serialized_metadata)
    with (snapshot_dir / "content.md").open(
        "w", encoding="utf-8", newline=""
    ) as content_file:
        content_file.write(content)

    return snapshot_dir


def load_parse_snapshot(snapshot_dir: Path) -> ParseSnapshot:
    """Load and validate a persisted parse snapshot.

    Args:
        snapshot_dir: Directory containing snapshot metadata and content.

    Returns:
        The parsed snapshot metadata and complete Markdown content.

    Raises:
        FileNotFoundError: If either snapshot file is missing.
        ValueError: If metadata TOML is malformed or invalid.
    """
    metadata_path = snapshot_dir / "metadata.toml"
    content_path = snapshot_dir / "content.md"
    with metadata_path.open("rb") as metadata_file:
        try:
            data: Any = tomllib.load(metadata_file)
        except tomllib.TOMLDecodeError as error:
            raise ValueError("invalid parse snapshot metadata TOML") from error
    with content_path.open(encoding="utf-8", newline="") as content_file:
        content = content_file.read()

    if not isinstance(data, dict):
        raise ValueError("parse snapshot metadata must be a mapping")

    try:
        metadata = ParseSnapshotMetadata.model_validate(data)
    except ValidationError as error:
        raise ValueError("invalid parse snapshot metadata") from error

    if metadata.parse_id != snapshot_dir.name:
        raise ValueError("parse ID does not match snapshot directory name")
    if metadata.source.removeprefix("sha256:") != snapshot_dir.parent.name:
        raise ValueError("source digest does not match snapshot directory parent")

    return ParseSnapshot(metadata=metadata, content=content)
