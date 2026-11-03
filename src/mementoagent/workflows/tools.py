"""Memento application tools and per-session context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from mementoagent.agents import Agent, Tool
from mementoagent.capabilities.achievement import (
    AchievementDraft,
    materialize_achievement,
)
from mementoagent.capabilities.achievement.extraction import (
    extract_achievement as extract_capability,
)
from mementoagent.parsers import Parser, parse_and_save_snapshot
from mementoagent.schema import AchievementItem, ParseSnapshot
from mementoagent.validation import validate_record
from mementoagent.workspace import import_source, load_parse_snapshot, save_record


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


@dataclass
class MementoContext:
    """Mutable state scoped to one Memento Agent session."""

    workspace_root: Path
    parser: Parser
    extraction_agent: Agent
    snapshot: ParseSnapshot | None = None
    draft: AchievementDraft | None = None


class MementoToolset:
    """Build tools bound to one Memento application context."""

    def __init__(self, context: MementoContext) -> None:
        """Bind the tool handlers to one workspace session."""
        self._context = context

    def tools(self) -> tuple[Tool[Any], ...]:
        """Return the semantic tools available to the Memento Agent."""
        return (
            Tool(
                name="list_inbox",
                description="List files currently available in the workspace inbox.",
                parameters=_NoArguments,
                handler=self.list_inbox,
            ),
            Tool(
                name="prepare_source",
                description=(
                    "Import and parse one file from the workspace inbox, "
                    "then keep its snapshot available for extraction."
                    "The file is moved into content-addressed source storage."
                ),
                parameters=_FilenameArguments,
                handler=self.prepare_source,
            ),
            Tool(
                name="extract_achievement",
                description=(
                    "Extract one achievement from the currently prepared parse snapshot."
                ),
                parameters=_NoArguments,
                handler=self.extract_achievement,
            ),
            Tool(
                name="save_achievement",
                description=(
                    "Save a complete user-confirmed achievement using the "
                    "source from the current draft."
                ),
                parameters=_SaveAchievementArguments,
                handler=self.save_achievement,
            ),
        )

    def list_inbox(self, _arguments: _NoArguments) -> list[str]:
        """List files currently available in the workspace inbox."""
        inbox = self._context.workspace_root / "inbox"
        return sorted(
            path.relative_to(inbox).as_posix()
            for path in inbox.rglob("*")
            if path.is_file()
        )

    def prepare_source(self, arguments: _FilenameArguments) -> dict[str, str]:
        """Import and parse one file from the workspace inbox."""
        relative_path = Path(arguments.filename)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("filename must be relative to the workspace inbox")

        source_path = self._context.workspace_root / "inbox" / relative_path
        if not source_path.is_file():
            raise FileNotFoundError(arguments.filename)

        source = import_source(self._context.workspace_root, source_path)
        snapshot_dir = parse_and_save_snapshot(
            self._context.workspace_root, source, self._context.parser
        )
        snapshot = load_parse_snapshot(snapshot_dir)
        self._context.snapshot = snapshot
        self._context.draft = None
        return {
            "source": snapshot.metadata.source,
            "parse_id": snapshot.metadata.parse_id,
            "parser": snapshot.metadata.parser,
            "parser_version": snapshot.metadata.parser_version,
        }

    def extract_achievement(self, _arguments: _NoArguments) -> dict[str, Any]:
        """Extract one achievement from the prepared parse snapshot."""
        snapshot = self._context.snapshot
        if snapshot is None:
            raise ValueError("prepare a source before extracting an achievement")

        self._context.draft = extract_capability(
            self._context.extraction_agent, snapshot
        )
        return self._context.draft.model_dump(mode="json")

    def save_achievement(self, arguments: _SaveAchievementArguments) -> str:
        """Save a complete user-confirmed achievement."""
        if self._context.draft is None:
            raise ValueError("extract an achievement before saving it")

        record = materialize_achievement(self._context.draft, arguments.data)
        errors = validate_record(self._context.workspace_root, record)
        if errors:
            raise ValueError("record validation failed")
        return str(save_record(self._context.workspace_root, record))
