"""A synchronous Responses API function-tool loop."""

import json
from collections.abc import Sequence
from typing import Any, TypeVar

from openai import OpenAI, omit
from pydantic import BaseModel, ValidationError

from ..conversation import Conversation
from .tools import Tool

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredOutputError(ValueError):
    """Raised when a completed response has no valid structured output."""


class Agent:
    """Execute the function tools chosen by a model."""

    def __init__(
        self,
        client: OpenAI,
        model: str,
        instructions: str,
        tools: Sequence[Tool[Any]] = (),
        max_model_calls: int = 8,
    ) -> None:
        """Configure an Agent with a caller-owned client.

        Args:
            client: OpenAI client created and closed by the caller.
            model: Model used for every request.
            instructions: System instructions sent with every request.
            tools: Functions the model may call.
            max_model_calls: Maximum model requests per `run()` call.
        """
        self.client = client
        self.model = model
        self.instructions = instructions
        self.tools = tuple(tools)
        self.max_model_calls = max_model_calls

    def run(self, user_input: str, *, conversation: Conversation) -> str:
        """Respond to a user message, calling tools when requested.

        Args:
            user_input: New user message in this conversation.
            conversation: In-memory history to continue and update.

        Returns:
            The model's final text response.

        Raises:
            RuntimeError: If the model request limit is exhausted.

        API errors propagate to the caller. Tool failures are returned to the
        model as function outputs. Conversation history is committed only
        after a completed final response. Tool side effects are not rolled
        back if the turn fails.
        """
        items = [*conversation._items, {"role": "user", "content": user_input}]
        tool_by_name = {tool.name: tool for tool in self.tools}
        definitions = [tool.definition() for tool in self.tools]

        for call_number in range(self.max_model_calls):
            response = self.client.responses.create(
                model=self.model,
                instructions=self.instructions,
                input=items,
                tools=definitions or omit,
            )
            if response.status != "completed":
                raise RuntimeError(
                    f"model response did not complete (status: {response.status})"
                )
            items.extend(response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                conversation._items = items
                return response.output_text
            if call_number == self.max_model_calls - 1:
                raise RuntimeError("model request limit exhausted")

            for call in calls:
                tool = tool_by_name.get(call.name)
                if tool is None:
                    output = json.dumps(
                        {
                            "error": {
                                "kind": "unknown_tool",
                                "message": "This tool is not available. Choose a declared tool.",
                            }
                        },
                        ensure_ascii=False,
                    )
                else:
                    output = tool.execute(call.arguments)
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output,
                    }
                )

        raise RuntimeError("model request limit exhausted")

    def run_structured(
        self,
        user_input: str,
        output_type: type[OutputT],
        *,
        instructions: str | None = None,
    ) -> OutputT:
        """Run one request and parse its final response as a Pydantic model.

        Args:
            user_input: Input sent to the model.
            output_type: Pydantic model required from the final response.
            instructions: Optional instructions replacing the Agent defaults.

        Returns:
            The validated structured response.

        Raises:
            StructuredOutputError: If the response is incomplete, refused, or
                does not contain valid structured output.
        """
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=self.instructions
                if instructions is None
                else instructions,
                input=user_input,
                text_format=output_type,
            )
        except ValidationError as error:
            raise StructuredOutputError(
                "model response did not match the requested structured output"
            ) from error

        if response.status != "completed":
            raise StructuredOutputError(
                f"model response did not complete (status: {response.status})"
            )
        parsed = response.output_parsed
        if parsed is None:
            raise StructuredOutputError("model response contained no structured output")
        return parsed
