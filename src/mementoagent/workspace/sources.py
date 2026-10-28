"""Import source files into a workspace's content-addressed storage."""

import hashlib
import shutil
from pathlib import Path


def import_source(workspace_root: Path, file_path: Path) -> str:
    """Import a file into the workspace's content-addressed storage.

    Args:
        workspace_root: Absolute path to the workspace root.
        file_path: Path to the file to import.

    Returns:
        Hash identifier in `sha256:<64 hex chars>` format.

    Raises:
        ValueError: If `workspace_root` is not absolute.
        FileNotFoundError: If `file_path` does not exist or is not a file.
    """
    if not workspace_root.is_absolute():
        raise ValueError("workspace_root must be absolute")

    source_path = file_path.expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    digest_builder = hashlib.sha256()
    with source_path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest_builder.update(chunk)
    digest = digest_builder.hexdigest()

    destination_directory = workspace_root / "sources" / digest[:2]
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = destination_directory / f"{digest}{source_path.suffix}"

    if not destination.exists():
        shutil.move(str(source_path), str(destination))

    return f"sha256:{digest}"
