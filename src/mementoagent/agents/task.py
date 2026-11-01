"""Generic task declarations for the Memento Agent runtime."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

from .tools import ToolSpec

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", bound=BaseModel, covariant=True)


class AgentTask(Protocol, Generic[InputT, OutputT]):
    """Describe one typed task that can be executed by the runtime."""

    @property
    def name(self) -> str:
        """Return the stable task name."""
        ...

    @property
    def description(self) -> str:
        """Return the task description used for composition."""
        ...

    @property
    def instructions(self) -> str:
        """Return the model instructions for this task."""
        ...

    @property
    def output_type(self) -> type[OutputT]:
        """Return the Pydantic type expected from the task."""
        ...

    @property
    def model(self) -> str | None:
        """Return an optional model override."""
        ...

    def build_input(self, value: InputT) -> str:
        """Convert a task value into model input text."""
        ...

    def tools(self) -> Sequence[ToolSpec[Any]]:
        """Return the tools available during the task."""
        ...

    def subagents(self) -> Sequence[AgentTask[str, Any]]:
        """Return specialist tasks exposed as internal tools."""
        ...


def _empty_tools() -> Sequence[ToolSpec[Any]]:
    return ()


def _empty_subagents() -> Sequence[AgentTask[str, Any]]:
    return ()


@dataclass(frozen=True)
class TaskSpec(Generic[InputT, OutputT]):
    """Declare a task without creating a task-specific Agent class."""

    name: str
    description: str
    instructions: str
    output_type: type[OutputT]
    input_builder: Callable[[InputT], str]
    model: str | None = None
    tool_builder: Callable[[], Sequence[ToolSpec[Any]]] = _empty_tools
    subagent_builder: Callable[[], Sequence[AgentTask[str, Any]]] = _empty_subagents

    def build_input(self, value: InputT) -> str:
        """Build model input using the declared input builder."""
        return self.input_builder(value)

    def tools(self) -> Sequence[ToolSpec[Any]]:
        """Return tools from the declared tool builder."""
        return self.tool_builder()

    def subagents(self) -> Sequence[AgentTask[str, Any]]:
        """Return subagents from the declared subagent builder."""
        return self.subagent_builder()
