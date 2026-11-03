"""Function tools available to an Agent."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from openai import pydantic_responses_function_tool
from openai.types.responses import FunctionToolParam
from pydantic import BaseModel, ValidationError

ParamsT = TypeVar("ParamsT", bound=BaseModel)


class ToolError(Exception):
    """An expected tool failure with a message safe to show the model."""


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
        try:
            arguments = self.parameters.model_validate_json(arguments_json)
        except ValidationError as error:
            details = [
                {
                    "location": ".".join(str(part) for part in item["loc"]),
                    "message": item["msg"],
                }
                for item in error.errors(include_input=False, include_context=False)
            ]
            return json.dumps(
                {
                    "error": {
                        "kind": "invalid_arguments",
                        "message": "Tool arguments did not match the required schema.",
                        "details": details,
                    }
                },
                ensure_ascii=False,
            )

        try:
            result = self.handler(arguments)
            return json.dumps(result, ensure_ascii=False)
        except ToolError as error:
            return json.dumps(
                {"error": {"kind": "tool_error", "message": str(error)}},
                ensure_ascii=False,
            )
        except Exception:
            return json.dumps(
                {
                    "error": {
                        "kind": "tool_execution_failed",
                        "message": "The tool failed. Please try a different approach.",
                    }
                },
                ensure_ascii=False,
            )
