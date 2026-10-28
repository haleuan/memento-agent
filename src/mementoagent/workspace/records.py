"""Record file I/O with YAML front matter and Markdown body."""

from pathlib import Path
from typing import Any, TypeVar, cast

import yaml
from pydantic import BaseModel, ValidationError

from mementoagent.schema import RecordEnvelope


RecordData = TypeVar("RecordData", bound=BaseModel)


def save_record(workspace_root: Path, record: RecordEnvelope[Any]) -> Path:
    """Save a record as YAML front matter followed by a Markdown body.

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
    path = workspace_root / "records" / record_type / f"{record.id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)

    data = record.model_dump(by_alias=True, mode="json")
    body = data.pop("body", "")
    front_matter = yaml.dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    content = f"---\n{front_matter}---\n"
    if body:
        content += f"\n{body}"
    path.write_text(content, encoding="utf-8")
    return path


def load_record(
    path: Path,
    record_type: type[RecordData],
) -> RecordEnvelope[RecordData]:
    """Load a record from YAML front matter followed by a Markdown body.

    Args:
        path: Path to the record file.
        record_type: Type of the data payload.

    Returns:
        The parsed and validated record.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is invalid or validation fails.
    """
    content = path.read_text(encoding="utf-8")
    sections = content.split("---\n", 2)
    if len(sections) != 3 or sections[0]:
        raise ValueError("record must contain YAML front matter")

    try:
        data = yaml.safe_load(sections[1])
    except yaml.YAMLError as error:
        raise ValueError("invalid YAML front matter") from error
    if not isinstance(data, dict):
        raise ValueError("YAML front matter must be a mapping")

    body = sections[2]
    if body.startswith("\n"):
        body = body[1:]
    data["body"] = body

    payload_type = record_type
    try:
        return cast(
            RecordEnvelope[RecordData],
            RecordEnvelope[payload_type].model_validate(data),
        )
    except ValidationError as error:
        raise ValueError("invalid record") from error
