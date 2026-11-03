"""A synchronous Responses API tool loop with in-memory conversation history."""

from collections.abc import Sequence
from typing import Any

from openai import OpenAI, omit

from .tools import Tool


class Agent:
    """Keep a conversation and execute the function tools chosen by a model."""

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
        self.history: list[Any] = []

    def run(self, user_input: str) -> str:
        """Respond to a user message, calling tools when requested.

        Args:
            user_input: New user message in this conversation.

        Returns:
            The model's final text response.

        Raises:
            RuntimeError: If the model request limit is exhausted.

        API, argument validation, and tool errors propagate to the caller.
        History is committed only after a final response. Tool side effects
        are not rolled back when a call fails.
        """
        items = [*self.history, {"role": "user", "content": user_input}]
        tool_by_name = {tool.name: tool for tool in self.tools}
        definitions = [tool.definition() for tool in self.tools]

        for call_number in range(self.max_model_calls):
            response = self.client.responses.create(
                model=self.model,
                instructions=self.instructions,
                input=items,
                tools=definitions or omit,
            )
            items.extend(response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                self.history = items
                return response.output_text
            if call_number == self.max_model_calls - 1:
                raise RuntimeError("model request limit exhausted")

            for call in calls:
                output = tool_by_name[call.name].execute(call.arguments)
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output,
                    }
                )

        raise RuntimeError("model request limit exhausted")
