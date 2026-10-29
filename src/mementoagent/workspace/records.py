"""Record file I/O using TOML."""

from pathlib import Path
import tomllib
from typing import Any, TypeVar, cast

from pydantic import BaseModel, ValidationError
import tomli_w

from mementoagent.schema import RecordEnvelope


RecordData = TypeVar("RecordData", bound=BaseModel)


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
    try:
        with path.open("rb") as record_file:
            data = tomllib.load(record_file)
    except tomllib.TOMLDecodeError as error:
        raise ValueError("invalid TOML record") from error

    try:
        return cast(
            RecordEnvelope[RecordData],
            RecordEnvelope[record_type].model_validate(data),
        )
    except ValidationError as error:
        raise ValueError("invalid record") from error
