"""Record file I/O using TOML."""

import tomllib
from pathlib import Path
from typing import Any, TypeVar, cast

import tomli_w
from pydantic import BaseModel, ValidationError

from mementoagent.schema import RecordEnvelope

RecordData = TypeVar("RecordData", bound=BaseModel)


def iter_record_paths(workspace_root: Path) -> list[Path]:
    """Return persisted record paths in deterministic order.

    Args:
        workspace_root: Absolute workspace root containing the `records` directory.

    Returns:
        Record TOML paths sorted by their workspace-relative path.

    Raises:
        ValueError: If `workspace_root` is not absolute.
    """
    if not workspace_root.is_absolute():
        raise ValueError("workspace_root must be absolute")

    records_root = workspace_root / "records"
    if not records_root.is_dir():
        return []

    return sorted(path for path in records_root.glob("*/*.toml") if path.is_file())


def load_raw_record(path: Path) -> dict[str, object]:
    """Load a record TOML document without validating its payload schema.

    Args:
        path: TOML record path.

    Returns:
        Parsed top-level TOML mapping.

    Raises:
        FileNotFoundError: If `path` does not exist.
        ValueError: If the file is not valid UTF-8 TOML.
    """
    try:
        with path.open("rb") as record_file:
            return tomllib.load(record_file)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ValueError("invalid TOML record") from error


def save_record(workspace_root: Path, record: RecordEnvelope[Any]) -> Path:
    """Save a record as a TOML document.

    Args:
        workspace_root: Absolute path to the workspace root.
        record: The record to save.

    Returns:
        Absolute path to the saved file.

    Raises:
        ValueError: If workspace_root is not absolute.
    """
    if not workspace_root.is_absolute():
        raise ValueError("workspace_root must be absolute")

    record_type = record.schema_version.split("/", 1)[0]
    path = workspace_root / "records" / record_type / f"{record.id}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)

    data = record.model_dump(by_alias=True, mode="json", exclude_none=True)
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path


def load_record(
    path: Path,
    record_type: type[RecordData],
) -> RecordEnvelope[RecordData]:
    """Load a record from a TOML file.

    Args:
        path: Path to the record file.
        record_type: Type of the data payload.

    Returns:
        The parsed and validated record.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is invalid or validation fails.
    """
    data = load_raw_record(path)

    try:
        return cast(
            RecordEnvelope[RecordData],
            RecordEnvelope[record_type].model_validate(data),
        )
    except ValidationError as error:
        raise ValueError("invalid record") from error
