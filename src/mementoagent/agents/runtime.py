"""A small synchronous Agent runtime built on the OpenAI Python SDK."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar, cast

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .base import BaseAgent
from .tools import ToolSpec


OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentRuntimeError(RuntimeError):
    """Raised when a model run cannot produce the requested output."""


@dataclass
class RunState:
    """Ephemeral state for one runtime invocation."""

    input_items: list[Any]
    context: object | None = None
    turns: int = 0
    tool_calls: int = 0
    tool_outputs: list[Any] = field(default_factory=list)


class _SubagentArguments(BaseModel):
    """Arguments accepted by an internal subagent tool."""

    input: str


class AgentRuntime(Generic[OutputT]):
    """Run typed task Agents through the OpenAI Responses API."""

    def __init__(
        self,
        model: str,
        *,
        client: OpenAI | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_turns: int = 1,
        max_tool_calls: int = 8,
    ) -> None:
        """Initialize a synchronous runtime.

        Args:
            model: Default model used when a task does not override it.
            client: Optional preconfigured OpenAI client, useful for tests.
            api_key: API key used when the runtime creates a client.
            base_url: Optional OpenAI-compatible endpoint.
            max_turns: Maximum number of model requests per run.
            max_tool_calls: Maximum number of function tools per run.
        """
        if max_turns < 1 or max_tool_calls < 0:
            raise ValueError("runtime limits must be non-negative and usable")
        self._model = model
        self._client = client or OpenAI(api_key=api_key, base_url=base_url)
        self._max_turns = max_turns
        self._max_tool_calls = max_tool_calls

    def run(
        self,
        agent: BaseAgent[Any, OutputT],
        value: Any,
        *,
        context: object | None = None,
    ) -> OutputT:
        """Run an Agent and return only its validated structured output.

        Args:
            agent: Typed task declaration.
            value: Domain input converted by the task.
            context: Optional opaque context passed to tool handlers.

        Returns:
            The task's Pydantic output.

        Raises:
            AgentRuntimeError: If the request, tool loop, or output fails.
        """
        tools = self._collect_tools(agent)
        tool_by_name = {tool.name: tool for tool in tools}
        state = RunState([agent.build_input(value)], context=context)

        while state.turns < self._max_turns:
            state.turns += 1
            try:
                request: dict[str, Any] = {
                    "model": agent.model or self._model,
                    "instructions": agent.instructions,
                    "input": state.input_items[0]
                    if state.turns == 1
                    else state.input_items,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": agent.output_type.__name__,
                            "strict": True,
                            "schema": agent.output_type.model_json_schema(),
                        }
                    },
                }
                definitions = self._tool_definitions(tools)
                if definitions:
                    request["tools"] = definitions
                response = self._client.responses.create(**request)
            except Exception as error:
                raise AgentRuntimeError("model request failed") from error

            output_items = self._response_output(response)
            function_calls = [
                item
                for item in output_items
                if self._item_value(item, "type") == "function_call"
            ]
            if function_calls:
                if state.turns >= self._max_turns:
                    raise AgentRuntimeError("model did not return final output")
                state.input_items.extend(self._serialize_items(output_items))
                for call in function_calls:
                    state.tool_calls += 1
                    if state.tool_calls > self._max_tool_calls:
                        raise AgentRuntimeError("tool call limit exceeded")
                    tool_output = self._execute_tool(call, tool_by_name, state.context)
                    state.tool_outputs.append(tool_output)
                    state.input_items.append(tool_output)
                continue

            return self._parse_output(response, agent.output_type)

        raise AgentRuntimeError("model did not return final output")

    def _collect_tools(self, agent: BaseAgent[Any, Any]) -> list[ToolSpec]:
        tools = list(agent.tools())
        for subagent in agent.subagents():
            tools.append(self._subagent_tool(subagent))
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise AgentRuntimeError("duplicate tool name")
        return tools

    def _subagent_tool(self, agent: BaseAgent[Any, Any]) -> ToolSpec:
        def run_subagent(arguments: BaseModel, context: object | None) -> object:
            parsed = cast(_SubagentArguments, arguments)
            return self.run(agent, parsed.input, context=context).model_dump(
                mode="json"
            )

        return ToolSpec(
            name=agent.name,
            description=agent.description,
            parameters=_SubagentArguments,
            handler=run_subagent,
        )

    def _tool_definitions(self, tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters.model_json_schema(),
                "strict": True,
            }
            for tool in tools
        ]

    def _execute_tool(
        self,
        call: Any,
        tool_by_name: dict[str, ToolSpec],
        context: object | None,
    ) -> dict[str, str]:
        name = self._item_value(call, "name")
        tool = tool_by_name.get(name)
        if tool is None:
            raise AgentRuntimeError("unknown tool")
        try:
            arguments = tool.parameters.model_validate_json(
                self._item_value(call, "arguments")
            )
            result = tool.handler(arguments, context)
            output = json.dumps(result, ensure_ascii=False)
        except Exception as error:
            raise AgentRuntimeError("tool execution failed") from error
        return {
            "type": "function_call_output",
            "call_id": self._item_value(call, "call_id"),
            "output": output,
        }

    def _parse_output(self, response: Any, output_type: type[OutputT]) -> OutputT:
        text = self._item_value(response, "output_text")
        if not isinstance(text, str) or not text:
            raise AgentRuntimeError("model returned no structured output")
        try:
            return output_type.model_validate_json(text)
        except (ValidationError, ValueError, TypeError) as error:
            raise AgentRuntimeError("invalid structured output") from error

    @staticmethod
    def _response_output(response: Any) -> list[Any]:
        output = AgentRuntime._item_value(response, "output")
        if not isinstance(output, Sequence) or isinstance(output, (str, bytes)):
            return []
        return list(output)

    @staticmethod
    def _serialize_items(items: Sequence[Any]) -> list[Any]:
        serialized: list[Any] = []
        for item in items:
            if isinstance(item, dict):
                serialized.append(item)
                continue
            dump = getattr(item, "model_dump", None)
            serialized.append(
                dump(mode="json", exclude_none=True) if callable(dump) else vars(item)
            )
        return serialized

    @staticmethod
    def _item_value(item: Any, key: str) -> Any:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)
