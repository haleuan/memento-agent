"""Base declarations for structured Memento agents."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Declare one structured agent task without owning its runtime."""

    name: str
    description: str
    instructions: str
    output_type: type[OutputT]
    model: str | None = None

    @abstractmethod
    def build_input(self, value: InputT) -> str:
        """Build the model input for one task value.

        Args:
            value: Domain input for the task.

        Returns:
            Text input passed to the model runtime.
        """
        ...

    def subagents(self) -> Sequence["BaseAgent[Any, Any]"]:
        """Return specialist agents exposed as tools to this agent."""
        return ()
