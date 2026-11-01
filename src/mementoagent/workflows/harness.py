"""Application-level Agent harness for the Memento workspace."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

from mementoagent.agents import (
    AgentEvent,
    AgentRuntime,
    AgentSession,
    AgentTask,
    AgentTurn,
    ToolSpec,
)
from mementoagent.parsers import Parser

from .tools import MementoContext, MementoToolset

_MEMENTO_INSTRUCTIONS = """You are the Memento personal memory assistant.
Understand the user's intent and choose tools when workspace actions are needed.
Do not claim that an action succeeded before its tool returns successfully.
Use the available source and extraction tools to understand documents, then
explain the extracted facts and any description suggestion in natural language.
Ask the user for clear confirmation before saving a record. The user may
correct facts or provide a description; submit the complete corrected
AchievementItem to the save tool. Do not invent facts that are absent from the
document, and do not modify source provenance or evidence. The user may ask to
inspect a document without saving it. Explain unsupported requests instead of
performing unrelated actions.
"""


class MementoAgent:
    """User-facing Agent definition and in-memory application harness."""

    name = "memento"
    description = "Manage source-backed personal memory records."
    instructions = _MEMENTO_INSTRUCTIONS
    model = None
    max_turns = 8
    max_tool_calls = 16

    def __init__(
        self,
        workspace_root: Path,
        parser: Parser,
        runtime: AgentRuntime,
    ) -> None:
        """Initialize one isolated Memento Agent session.

        Args:
            workspace_root: Absolute workspace root used by capability tools.
            parser: Parser used when the Agent prepares an inbox source.
            runtime: Runtime used for the conversational Agent and extraction.
        """
        self._context = MementoContext(
            workspace_root=workspace_root,
            parser=parser,
            runtime=runtime,
        )
        self._toolset = MementoToolset(self._context)
        self._session = AgentSession(context=self._context)

    def tools(self) -> Sequence[ToolSpec[Any]]:
        """Return semantic workspace and achievement tools."""
        return self._toolset.specs()

    def subagents(self) -> Sequence[AgentTask[str, Any]]:
        """Return no concrete subagents in the first application version."""
        return ()

    def send(
        self,
        user_input: str,
        *,
        on_event: Callable[[AgentEvent], None] | None = None,
    ) -> AgentTurn:
        """Send one user turn to the Agent.

        Args:
            user_input: Natural-language user message.
            on_event: Optional callback receiving safe runtime events.

        Returns:
            The final Agent response for this turn.
        """
        return self._context.runtime.run_turn(
            self,
            self._session,
            user_input,
            on_event=on_event,
        )
