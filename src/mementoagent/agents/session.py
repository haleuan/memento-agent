"""In-memory conversation state for the Memento Agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from openai.types.responses import ParsedResponseOutputItem, ResponseInputItemParam

AgentEventKind = Literal["model_request", "tool_call", "tool_result"]


@dataclass(frozen=True)
class AgentEvent:
    """Safe metadata emitted while a conversational turn is running.

    Args:
        kind: Runtime phase that produced the event.
        tool_name: Tool name for tool events, or `None` for model requests.
    """

    kind: AgentEventKind
    tool_name: str | None = None


@dataclass(frozen=True)
class AgentTurn:
    """User-facing result of one completed conversational turn."""

    text: str


@dataclass
class AgentSession:
    """Ephemeral local replay state for one conversational Agent."""

    context: object | None = None
    input_items: list[ResponseInputItemParam | ParsedResponseOutputItem[Any]] = field(
        default_factory=list
    )
