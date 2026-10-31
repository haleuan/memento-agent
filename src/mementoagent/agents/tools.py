"""Explicit function tool declarations for the agent runtime."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

ParamsT = TypeVar("ParamsT", bound=BaseModel)


@dataclass(frozen=True)
class ToolSpec(Generic[ParamsT]):
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
    parameters: type[ParamsT]
    handler: Callable[[ParamsT, object | None], object]
