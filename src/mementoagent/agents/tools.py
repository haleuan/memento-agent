"""Explicit function tool declarations for the agent runtime."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel


ToolHandler = Callable[[BaseModel, object | None], object]


@dataclass(frozen=True)
class ToolSpec:
    """Describe one function tool exposed to a task Agent.

    Args:
        name: Stable function name sent to the model.
        description: Short explanation of when the model should call it.
        parameters: Pydantic model used to validate function arguments.
        handler: Synchronous implementation receiving validated parameters and
            optional run context.
    """

    name: str
    description: str
    parameters: type[BaseModel]
    handler: ToolHandler

    @property
    def parameter_model(self) -> type[BaseModel]:
        """Return the parameter model under an explicit descriptive name."""
        return self.parameters
