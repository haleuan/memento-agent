"""Runtime notifications for external Agent adapters."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AgentEvent:
    """Report progress without exposing model protocol items or tool payloads.

    Args:
        kind: Model request, visible text increment, or tool dispatch stage.
        delta: Visible text for a `text_delta` event.
        tool_name: Tool name for a `tool_call` or `tool_result` event.
        call_id: Identifier pairing a tool call with its returned result.

    A `tool_result` event means an output was produced, including error outputs.
    """

    kind: Literal["model_request", "text_delta", "tool_call", "tool_result"]
    delta: str | None = None
    tool_name: str | None = None
    call_id: str | None = None
