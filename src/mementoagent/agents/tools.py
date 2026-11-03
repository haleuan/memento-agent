"""Function tools available to an Agent."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from openai import pydantic_responses_function_tool
from openai.types.responses import FunctionToolParam
from pydantic import BaseModel

ParamsT = TypeVar("ParamsT", bound=BaseModel)


@dataclass(frozen=True)
class Tool(Generic[ParamsT]):
    """Describe a function and its validated arguments.

    Args:
        name: Stable function name sent to the model.
        description: Short explanation of when the model should call it.
        parameters: Pydantic model used to validate function arguments.
        handler: Function receiving the validated parameters and returning a
            JSON-serializable result.
    """

    name: str
    description: str
    parameters: type[ParamsT]
    handler: Callable[[ParamsT], object]

    def definition(self) -> FunctionToolParam:
        """Return the Responses API declaration for this tool."""
        return pydantic_responses_function_tool(
            self.parameters, name=self.name, description=self.description
        )

    def execute(self, arguments_json: str) -> str:
        """Validate arguments, execute the handler, and serialize its result.

        Args:
            arguments_json: JSON arguments supplied by the model.

        Returns:
            The handler result serialized as JSON.
        """
        arguments = self.parameters.model_validate_json(arguments_json)
        return json.dumps(self.handler(arguments), ensure_ascii=False)
