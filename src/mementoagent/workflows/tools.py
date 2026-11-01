"""Memento application tools and per-session context."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from mementoagent.agents import AgentRuntime, ToolSpec
from mementoagent.capabilities.achievement import (
    AchievementDraft,
    materialize_achievement,
)
from mementoagent.capabilities.achievement import (
    extract_achievement as extract_capability,
)
from mementoagent.parsers import Parser, parse_and_save_snapshot
from mementoagent.schema import AchievementItem, ParseSnapshot, RecordId
from mementoagent.validation import validate_record
from mementoagent.workspace import (
    import_source,
    iter_record_paths,
    load_parse_snapshot,
    load_raw_record,
    save_record,
)


class _NoArguments(BaseModel):
    """Arguments for tools that take no user-controlled values."""

    model_config = ConfigDict(extra="forbid")


class _FilenameArguments(BaseModel):
    """Arguments for preparing one inbox file."""

    model_config = ConfigDict(extra="forbid")

    filename: StrictStr = Field(min_length=1)


class _SaveAchievementArguments(BaseModel):
    """Arguments for saving user-confirmed achievement data."""

    model_config = ConfigDict(extra="forbid")

    data: AchievementItem


class _RecordIdArguments(BaseModel):
    """Arguments for loading one record by its identifier."""

    model_config = ConfigDict(extra="forbid")

    record_id: RecordId


@dataclass
class MementoContext:
    """Mutable state scoped to one Memento Agent session."""

    workspace_root: Path
    parser: Parser
    runtime: AgentRuntime
    snapshot: ParseSnapshot | None = None
    draft: AchievementDraft | None = None

    @classmethod
    def require(cls, value: object | None) -> MementoContext:
        """Return a runtime context with the Memento session type."""
        if not isinstance(value, cls):
            raise TypeError("MementoContext is required")
        return value


class MementoToolset:
    """Build and execute tools using the Runtime-provided context."""

    def specs(self) -> Sequence[ToolSpec[Any]]:
        """Return the semantic tools available to the Memento Agent."""
        return (
            ToolSpec(
                name="list_inbox",
                description="List files currently available in the workspace inbox.",
                parameters=_NoArguments,
                handler=self.list_inbox,
            ),
            ToolSpec(
                name="prepare_source",
                description=(
                    "Import and parse one file from the workspace inbox, "
                    "then keep its snapshot available for extraction."
                ),
                parameters=_FilenameArguments,
                handler=self.prepare_source,
            ),
            ToolSpec(
                name="extract_achievement",
                description=(
                    "Extract one achievement from the currently prepared parse snapshot."
                ),
                parameters=_NoArguments,
                handler=self.extract_achievement,
            ),
            ToolSpec(
                name="save_achievement",
                description=(
                    "Save a complete user-confirmed achievement using the "
                    "source from the current draft."
                ),
                parameters=_SaveAchievementArguments,
                handler=self.save_achievement,
            ),
            ToolSpec(
                name="list_records",
                description="List stored records with generic metadata and summaries.",
                parameters=_NoArguments,
                handler=self.list_records,
            ),
            ToolSpec(
                name="get_record",
                description="Load one stored record by its record identifier.",
                parameters=_RecordIdArguments,
                handler=self.get_record,
            ),
        )

    def list_inbox(
        self,
        _arguments: _NoArguments,
        runtime_context: object | None,
    ) -> list[str]:
        """List files currently available in the workspace inbox."""
        context = MementoContext.require(runtime_context)
        inbox = context.workspace_root / "inbox"
        return sorted(
            path.relative_to(inbox).as_posix()
            for path in inbox.rglob("*")
            if path.is_file()
        )

    def prepare_source(
        self,
        arguments: _FilenameArguments,
        runtime_context: object | None,
    ) -> dict[str, str]:
        """Import and parse one file from the workspace inbox."""
        context = MementoContext.require(runtime_context)
        relative_path = Path(arguments.filename)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("filename must be relative to the workspace inbox")

        source_path = context.workspace_root / "inbox" / relative_path
        if not source_path.is_file():
            raise FileNotFoundError(arguments.filename)

        source = import_source(context.workspace_root, source_path)
        snapshot_dir = parse_and_save_snapshot(
            context.workspace_root, source, context.parser
        )
        snapshot = load_parse_snapshot(snapshot_dir)
        context.snapshot = snapshot
        context.draft = None
        return {
            "source": snapshot.metadata.source,
            "parse_id": snapshot.metadata.parse_id,
            "parser": snapshot.metadata.parser,
            "parser_version": snapshot.metadata.parser_version,
        }

    def extract_achievement(
        self,
        _arguments: _NoArguments,
        runtime_context: object | None,
    ) -> dict[str, Any]:
        """Extract one achievement from the prepared parse snapshot."""
        context = MementoContext.require(runtime_context)
        if context.snapshot is None:
            raise ValueError("prepare a source before extracting an achievement")

        context.draft = extract_capability(context.runtime, context.snapshot)
        return context.draft.model_dump(mode="json")

    def save_achievement(
        self,
        arguments: _SaveAchievementArguments,
        runtime_context: object | None,
    ) -> str:
        """Save a complete user-confirmed achievement."""
        context = MementoContext.require(runtime_context)
        if context.draft is None:
            raise ValueError("extract an achievement before saving it")

        record = materialize_achievement(context.draft, arguments.data)
        errors = validate_record(context.workspace_root, record)
        if errors:
            raise ValueError("record validation failed")
        return str(save_record(context.workspace_root, record))

    def list_records(
        self,
        _arguments: _NoArguments,
        runtime_context: object | None,
    ) -> list[dict[str, object]]:
        """List stored records with generic metadata and summaries."""
        context = MementoContext.require(runtime_context)
        summaries: list[dict[str, object]] = []
        for path in iter_record_paths(context.workspace_root):
            record = load_raw_record(path)
            data = record.get("data")
            summary: dict[str, object] = {}
            if isinstance(data, dict):
                if record.get("schema") == "achievement/1":
                    for key in ("title", "kind", "organization"):
                        item = data.get(key)
                        if isinstance(item, str):
                            summary[key] = item
                elif isinstance(data.get("title"), str):
                    summary["title"] = data["title"]

            summaries.append(
                {
                    "id": record.get("id"),
                    "schema": record.get("schema"),
                    "provenance": record.get("provenance"),
                    "created_at": record.get("created_at"),
                    "occurred": record.get("occurred"),
                    "path": path.relative_to(context.workspace_root).as_posix(),
                    "summary": summary,
                }
            )
        return summaries

    def get_record(
        self,
        arguments: _RecordIdArguments,
        runtime_context: object | None,
    ) -> dict[str, object]:
        """Load one stored record by its record identifier."""
        context = MementoContext.require(runtime_context)
        matches = [
            path
            for path in iter_record_paths(context.workspace_root)
            if path.stem == arguments.record_id
        ]
        if not matches:
            raise FileNotFoundError(arguments.record_id)
        if len(matches) > 1:
            raise ValueError("duplicate record identifier")
        return load_raw_record(matches[0])
