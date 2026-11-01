"""A small synchronous Agent runtime built on the OpenAI Python SDK."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self, cast

from openai import OpenAI, omit, pydantic_responses_function_tool
from openai.types.responses import (
    ParsedResponseFunctionToolCall,
    ParsedResponseOutputItem,
    ResponseFunctionToolCall,
    ResponseInputItemParam,
    ResponseInputParam,
)
from openai.types.responses.response_input_param import FunctionCallOutput
from pydantic import BaseModel, ConfigDict, StrictStr

from .session import AgentEvent, AgentSession, AgentTurn
from .task import AgentDefinition, AgentTask, InputT, OutputT
from .tools import ToolSpec


class AgentRuntimeError(RuntimeError):
    """Raised when a model run cannot produce the requested output."""


@dataclass
class RunState:
    """Ephemeral state for one runtime invocation."""

    input_items: list[ResponseInputItemParam | ParsedResponseOutputItem[Any]]
    context: object | None = None
    turns: int = 0
    tool_calls: int = 0


class _SubagentArguments(BaseModel):
    """Arguments accepted by an internal subagent tool."""

    model_config = ConfigDict(extra="forbid")

    input: StrictStr


class AgentRuntime:
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
            client: Optional client whose lifecycle remains with the caller.
            api_key: API key used when the runtime creates a client.
            base_url: Optional OpenAI-compatible endpoint.
            max_turns: Maximum number of model requests per run.
            max_tool_calls: Maximum number of function tools per run.
        """
        if max_turns < 1 or max_tool_calls < 0:
            raise ValueError("runtime limits must be non-negative and usable")
        self._model = model
        self._owns_client = client is None
        self._client = (
            client if client is not None else OpenAI(api_key=api_key, base_url=base_url)
        )
        self._max_turns = max_turns
        self._max_tool_calls = max_tool_calls

    def close(self) -> None:
        """Close the client when it was created by this runtime."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        """Return this runtime for a managed resource scope."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the owned client when leaving the resource scope."""
        self.close()

    def run(
        self,
        agent: AgentTask[InputT, OutputT],
        value: InputT,
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
        definitions = [
            pydantic_responses_function_tool(
                tool.parameters, name=tool.name, description=tool.description
            )
            for tool in tools
        ]
        state = RunState(
            [{"role": "user", "content": agent.build_input(value)}], context=context
        )

        max_turns = self._agent_limit(agent, "max_turns", self._max_turns)
        max_tool_calls = self._agent_limit(
            agent, "max_tool_calls", self._max_tool_calls
        )
        while state.turns < max_turns:
            state.turns += 1
            try:
                response = self._client.responses.parse(
                    model=agent.model or self._model,
                    instructions=agent.instructions,
                    input=cast(ResponseInputParam, state.input_items),
                    text_format=agent.output_type,
                    tools=definitions or omit,
                )
            except Exception as error:
                raise AgentRuntimeError("model request failed") from error

            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]
            if function_calls:
                if state.turns >= max_turns:
                    raise AgentRuntimeError("model did not return final output")
                state.input_items.extend(response.output)
                for call in function_calls:
                    state.tool_calls += 1
                    if state.tool_calls > max_tool_calls:
                        raise AgentRuntimeError("tool call limit exceeded")
                    state.input_items.append(
                        self._execute_tool(call, tool_by_name, state.context)
                    )
                continue

            if response.output_parsed is None:
                raise AgentRuntimeError("model returned no structured output")
            return response.output_parsed

        raise AgentRuntimeError("model did not return final output")

    def run_turn(
        self,
        agent: AgentDefinition,
        session: AgentSession,
        user_input: str,
        *,
        on_event: Callable[[AgentEvent], None] | None = None,
    ) -> AgentTurn:
        """Run one natural-language turn and retain its local history.

        Args:
            agent: Conversational Agent definition.
            session: In-memory replay state for the conversation.
            user_input: New user message for this turn.
            on_event: Optional callback receiving safe runtime metadata.

        Returns:
            The final assistant text for the turn.

        Raises:
            AgentRuntimeError: If the model cannot produce a final response or
                the runtime limits are exceeded.
        """
        session.input_items.append({"role": "user", "content": user_input})
        tools = self._collect_tools(agent)
        tool_by_name = {tool.name: tool for tool in tools}
        definitions = [
            pydantic_responses_function_tool(
                tool.parameters, name=tool.name, description=tool.description
            )
            for tool in tools
        ]
        max_turns = self._agent_limit(agent, "max_turns", self._max_turns)
        max_tool_calls = self._agent_limit(
            agent, "max_tool_calls", self._max_tool_calls
        )
        turns = 0
        tool_calls = 0

        while turns < max_turns:
            turns += 1
            self._emit(on_event, AgentEvent("model_request"))
            try:
                response = self._client.responses.create(
                    model=agent.model or self._model,
                    instructions=agent.instructions,
                    input=cast(ResponseInputParam, session.input_items),
                    tools=definitions or omit,
                )
            except Exception as error:
                raise AgentRuntimeError("model request failed") from error

            session.input_items.extend(cast(Any, response.output))
            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]
            if function_calls:
                if turns >= max_turns:
                    raise AgentRuntimeError("model did not return final output")
                for call in function_calls:
                    tool_calls += 1
                    if tool_calls > max_tool_calls:
                        raise AgentRuntimeError("tool call limit exceeded")
                    self._emit(on_event, AgentEvent("tool_call", call.name))
                    output = self._execute_conversational_tool(
                        call, tool_by_name, session.context
                    )
                    session.input_items.append(output)
                    self._emit(on_event, AgentEvent("tool_result", call.name))
                continue

            if not response.output_text:
                raise AgentRuntimeError("model returned no final text")
            return AgentTurn(text=response.output_text)

        raise AgentRuntimeError("model did not return final output")

    @staticmethod
    def _agent_limit(agent: object, attribute: str, default: int) -> int:
        value = getattr(agent, attribute, None)
        return default if value is None else value

    @staticmethod
    def _emit(
        callback: Callable[[AgentEvent], None] | None,
        event: AgentEvent,
    ) -> None:
        if callback is not None:
            callback(event)

    def _collect_tools(self, agent: object) -> list[ToolSpec[Any]]:
        tools = list(cast(AgentDefinition, agent).tools())
        for subagent in cast(AgentDefinition, agent).subagents():
            tools.append(self._subagent_tool(subagent))
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise AgentRuntimeError("duplicate tool name")
        return tools

    def _execute_conversational_tool(
        self,
        call: ResponseFunctionToolCall,
        tool_by_name: dict[str, ToolSpec[Any]],
        context: object | None,
    ) -> FunctionCallOutput:
        """Execute a conversational tool with a sanitized failure result."""
        tool = tool_by_name.get(call.name)
        if tool is None:
            return {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": "tool execution failed",
            }
        try:
            arguments = tool.parameters.model_validate_json(call.arguments)
            result = tool.handler(arguments, context)
            output = json.dumps(result, ensure_ascii=False)
        except Exception:
            output = "tool execution failed"
        return {
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": output,
        }

    def _subagent_tool(
        self, agent: AgentTask[str, Any]
    ) -> ToolSpec[_SubagentArguments]:
        def run_subagent(
            arguments: _SubagentArguments, context: object | None
        ) -> object:
            return self.run(agent, arguments.input, context=context).model_dump(
                mode="json"
            )

        return ToolSpec(
            name=agent.name,
            description=agent.description,
            parameters=_SubagentArguments,
            handler=run_subagent,
        )

    def _execute_tool(
        self,
        call: ParsedResponseFunctionToolCall,
        tool_by_name: dict[str, ToolSpec[Any]],
        context: object | None,
    ) -> FunctionCallOutput:
        tool = tool_by_name.get(call.name)
        if tool is None:
            raise AgentRuntimeError("unknown tool")
        try:
            result = tool.handler(call.parsed_arguments, context)
            output = json.dumps(result, ensure_ascii=False)
        except Exception as error:
            raise AgentRuntimeError("tool execution failed") from error
        return {
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": output,
        }
