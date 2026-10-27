"""Load typed records from pure TOML files without modifying them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any

from pydantic import ValidationError

from mementoagent.schema import AchievementData, RecordEnvelope


class RecordLoadError(ValueError):
    """An unreadable record or invalid record payload."""


class RecordSyntaxError(RecordLoadError):
    """A TOML syntax error with its source location when available."""

    def __init__(self, message: str, line: int | None, column: int | None) -> None:
        """Initialize a syntax error diagnostic.

        Args:
            message: TOML parser error description.
            line: One-based source line, when provided by the parser.
            column: One-based source column, when provided by the parser.
        """
        self.line = line
        self.column = column
        location = ""
        if line is not None:
            location = f" at line {line}"
            if column is not None:
                location += f", column {column}"
        super().__init__(f"Invalid TOML{location}: {message}")


@dataclass(frozen=True)
class LoadedRecord:
    """Typed record and optional narrative body loaded from a file."""

    record: RecordEnvelope[AchievementData]
    body: str


def load_record_file(path: Path | str) -> LoadedRecord:
    """Parse a TOML record, validate its schema, and retain its body.

    Args:
        path: Path to a `.toml` record file.

    Returns:
        The validated record and its optional narrative body.

    Raises:
        RecordLoadError: If the file extension, contents, or shape is invalid.
        RecordSyntaxError: If the file contains invalid TOML syntax.
    """
    path = Path(path)
    if path.suffix.lower() != ".toml":
        raise RecordLoadError("Record path must end with .toml")
    try:
        with path.open("rb") as handle:
            payload: Any = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        line = getattr(exc, "lineno", None)
        column = getattr(exc, "colno", None)
        if line is None:
            match = re.search(r"line (\d+), column (\d+)", str(exc))
            if match:
                line, column = map(int, match.groups())
        raise RecordSyntaxError(str(exc), line, column) from exc
    except OSError as exc:
        raise RecordLoadError(f"Unable to read record: {exc}") from exc

    body = payload.pop("body", "")
    if payload.get("schema") != "achievement/1":
        raise RecordLoadError(f"unsupported schema: {payload.get('schema')!r}")
    try:
        record = RecordEnvelope[AchievementData].model_validate(payload)
    except ValidationError as exc:
        messages = []
        for error in exc.errors(include_url=False):
            location = ".".join(str(part) for part in error["loc"])
            message = error["msg"]
            if error["type"] == "datetime_type":
                message = "timestamp must be quoted; quote the timestamp"
            if location in {"created_at", "verification.at"} and "timestamp" not in message:
                message = "timestamp must be quoted; quote the timestamp"
            messages.append(f"{location}: {message}")
        detail = "; ".join(messages)
        if any(message.startswith("occurred.body:") for message in messages):
            detail += "; top-level keys must precede table headers"
        raise RecordLoadError(detail) from exc
    if not isinstance(body, str):
        raise RecordLoadError("body must be a TOML string")
    return LoadedRecord(record=record, body=body)
