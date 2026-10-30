"""Connect parsers to persisted workspace snapshots."""

from pathlib import Path

from mementoagent.workspace import WorkspacePaths, save_parse_snapshot

from .base import Parser


def parse_and_save_snapshot(
    workspace_root: Path,
    source: str,
    parser: Parser,
) -> Path:
    """Parse an imported source and save its output as a snapshot.

    Args:
        workspace_root: Absolute path to the workspace root.
        source: Hash identifier of the imported source file.
        parser: Parser used to produce the snapshot content.

    Returns:
        The directory containing the saved parse snapshot.

    Raises:
        ValueError: If the workspace root is not absolute or the source hash is invalid.
        FileNotFoundError: If the source is not present in the workspace.
    """
    if not workspace_root.is_absolute():
        raise ValueError("workspace_root must be absolute")

    source_path = WorkspacePaths(workspace_root).find_source_file_by_hash(source)
    if source_path is None:
        raise FileNotFoundError(f"source file not found: {source}")

    content = parser.parse(source_path)
    return save_parse_snapshot(
        workspace_root=workspace_root,
        source=source,
        parser=parser.name,
        parser_version=parser.version,
        content=content,
    )
