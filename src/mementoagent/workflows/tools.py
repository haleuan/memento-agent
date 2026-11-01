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
    runtime: AgentRuntime
    snapshot: ParseSnapshot | None = None
    draft: AchievementDraft | None = None


def build_memento_tools() -> Sequence[ToolSpec[Any]]:
    """Build the semantic tools available to a Memento Agent."""
    return (
        ToolSpec(
            name="list_inbox",
            description="List files currently available in the workspace inbox.",
            parameters=_NoArguments,
            handler=_list_inbox,
        ),
        ToolSpec(
            name="prepare_source",
            description=(
                "Import and parse one file from the workspace inbox, "
                "then keep its snapshot available for extraction."
            ),
            parameters=_FilenameArguments,
            handler=_prepare_source,
        ),
        ToolSpec(
            name="extract_achievement",
            description=(
                "Extract one achievement from the currently prepared parse snapshot."
            ),
            parameters=_NoArguments,
            handler=_extract_achievement,
        ),
        ToolSpec(
            name="save_achievement",
            description=(
                "Save a complete user-confirmed achievement using the "
                "source from the current draft."
            ),
            parameters=_SaveAchievementArguments,
            handler=_save_achievement,
        ),
    )


def _context(value: object | None) -> MementoContext:
    if not isinstance(value, MementoContext):
        raise ValueError("Memento tools require an application context")
    return value


def _list_inbox(_arguments: _NoArguments, value: object | None) -> list[str]:
    context = _context(value)
    inbox = context.workspace_root / "inbox"
    return sorted(
        path.relative_to(inbox).as_posix()
        for path in inbox.rglob("*")
        if path.is_file()
    )


def _prepare_source(
    arguments: _FilenameArguments,
    value: object | None,
) -> dict[str, str]:
    context = _context(value)
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


def _extract_achievement(
    _arguments: _NoArguments,
    value: object | None,
) -> dict[str, Any]:
    context = _context(value)
    if context.snapshot is None:
        raise ValueError("prepare a source before extracting an achievement")

    context.draft = extract_capability(context.runtime, context.snapshot)
    return context.draft.model_dump(mode="json")


def _save_achievement(
    arguments: _SaveAchievementArguments,
    value: object | None,
) -> str:
    context = _context(value)
    if context.draft is None:
        raise ValueError("extract an achievement before saving it")

    record = materialize_achievement(context.draft, arguments.data)
    errors = validate_record(context.workspace_root, record)
    if errors:
        raise ValueError("record validation failed")
    return str(save_record(context.workspace_root, record))
