"""A small synchronous Agent runtime built on the OpenAI Python SDK."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self, cast

from openai import OpenAI, omit, pydantic_responses_function_tool
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseInputParam,
)
from openai.types.responses.response_input_param import FunctionCallOutput
from pydantic import BaseModel, ConfigDict, StrictStr

from .session import AgentEvent, AgentSession, AgentTurn
from .task import AgentDefinition, AgentTask, InputT, OutputT
from .tools import ToolSpec


class AgentRuntimeError(RuntimeError):
    """Raised when a model run cannot produce the requested output."""


class AgentStructuredOutputError(AgentRuntimeError):
    """Raised when a structured task has no valid final output."""


@dataclass
class RunState:
    """Ephemeral state for one runtime invocation."""

    input_items: list[Any]
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

    def run_structured_task(
        self,
        agent: AgentTask[InputT, OutputT],
        value: InputT,
        *,
        context: object | None = None,
    ) -> OutputT:
        """Run a structured task and return its validated output.

        Args:
            agent: Typed task declaration.
            value: Domain input converted by the task.
            context: Optional opaque context passed to tool handlers.

        Returns:
            The task's Pydantic output.

        Raises:
            AgentRuntimeError: If the request, tool loop, or output fails.
        """
        text = self._run_loop(
            cast(AgentDefinition, agent),
            [{"role": "user", "content": agent.build_input(value)}],
            context=context,
            output_type=agent.output_type,
        )
        try:
            return agent.output_type.model_validate_json(text)
        except Exception as error:
            raise AgentStructuredOutputError("invalid structured output") from error

    def run_conversation_turn(
        self,
        agent: AgentDefinition,
        session: AgentSession,
        user_input: str,
        *,
        on_event: Callable[[AgentEvent], None] | None = None,
        stream: bool = False,
    ) -> AgentTurn:
        """Run one conversational turn and retain its local history.

        Args:
            agent: Conversational Agent definition.
            session: In-memory replay state for the conversation.
            user_input: New user message for this turn.
            on_event: Optional callback receiving safe runtime metadata.
            stream: Whether to consume Responses streaming events.

        Returns:
            The final assistant text for the turn.

        Raises:
            AgentRuntimeError: If the model cannot produce a final response or
                the runtime limits are exceeded.
        """
        session.input_items.append({"role": "user", "content": user_input})
        text = self._run_loop(
            agent,
            session.input_items,
            context=session.context,
            on_event=on_event,
            stream=stream,
        )
        return AgentTurn(text=text)

    def _run_loop(
        self,
        agent: AgentDefinition,
        input_items: list[Any],
        *,
        context: object | None = None,
        output_type: type[BaseModel] | None = None,
        on_event: Callable[[AgentEvent], None] | None = None,
        stream: bool = False,
    ) -> str:
        """Run the shared Responses tool loop for one Agent invocation."""
        tools = self._collect_tools(agent)
        tool_by_name = {tool.name: tool for tool in tools}
        definitions = [
            pydantic_responses_function_tool(
                tool.parameters, name=tool.name, description=tool.description
            )
            for tool in tools
        ]
        state = RunState(input_items, context=context)
        max_turns = self._agent_limit(agent, "max_turns", self._max_turns)
        max_tool_calls = self._agent_limit(
            agent, "max_tool_calls", self._max_tool_calls
        )
        text_format = self._text_format(output_type)

        while state.turns < max_turns:
            state.turns += 1
            self._emit(on_event, AgentEvent("model_request"))
            try:
                output_items, output_text = self._request(
                    agent,
                    state.input_items,
                    definitions,
                    text_format,
                    stream=stream,
                    on_event=on_event,
                )
            except Exception as error:
                if isinstance(error, AgentRuntimeError):
                    raise
                raise AgentRuntimeError("model request failed") from error

            state.input_items.extend(output_items)
            function_calls = [
                item for item in output_items if item.type == "function_call"
            ]
            if function_calls:
                if state.turns >= max_turns:
                    raise AgentRuntimeError("model did not return final output")
                for call in function_calls:
                    state.tool_calls += 1
                    if state.tool_calls > max_tool_calls:
                        raise AgentRuntimeError("tool call limit exceeded")
                    self._emit(on_event, AgentEvent("tool_call", call.name))
                    output = self._execute_tool(
                        call,
                        tool_by_name,
                        state.context,
                        sanitize_errors=output_type is None,
                    )
                    state.input_items.append(output)
                    self._emit(on_event, AgentEvent("tool_result", call.name))
                continue

            if not output_text:
                raise AgentRuntimeError("model returned no final text")
            return output_text

        raise AgentRuntimeError("model did not return final output")

    @staticmethod
    def _text_format(
        output_type: type[BaseModel] | None,
    ) -> dict[str, object] | Any:
        if output_type is None:
            return omit
        schema = output_type.model_json_schema()
        AgentRuntime._make_schema_strict(schema)
        return {
            "format": {
                "type": "json_schema",
                "name": output_type.__name__,
                "schema": schema,
                "strict": True,
            }
        }

    @staticmethod
    def _make_schema_strict(schema: object) -> None:
        if isinstance(schema, dict):
            properties = schema.get("properties")
            if isinstance(properties, dict):
                schema["required"] = list(properties)
                schema["additionalProperties"] = False
            for value in schema.values():
                AgentRuntime._make_schema_strict(value)
        elif isinstance(schema, list):
            for value in schema:
                AgentRuntime._make_schema_strict(value)

    def _request(
        self,
        agent: AgentDefinition,
        input_items: list[Any],
        definitions: list[Any],
        text_format: dict[str, object] | Any,
        *,
        stream: bool,
        on_event: Callable[[AgentEvent], None] | None,
    ) -> tuple[list[Any], str]:
        request = {
            "model": agent.model or self._model,
            "instructions": agent.instructions,
            "input": cast(ResponseInputParam, input_items),
            "tools": definitions or omit,
            "text": text_format,
        }
        if not stream:
            response = self._client.responses.create(**request)
            return list(response.output), response.output_text or ""

        response_stream = self._client.responses.create(**request, stream=True)
        output_items: list[Any] = []
        text_parts: list[str] = []
        for raw_event in response_stream:
            event: Any = raw_event
            event_type = getattr(event, "type", None)
            if event_type == "response.output_text.delta":
                delta = event.delta
                text_parts.append(delta)
                self._emit(on_event, AgentEvent("text_delta", text=delta))
            elif event_type == "response.output_item.done":
                output_items.append(event.item)
            elif event_type == "error":
                raise AgentRuntimeError("model stream failed")
        return output_items, "".join(text_parts)

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

    def _execute_tool(
        self,
        call: ResponseFunctionToolCall,
        tool_by_name: dict[str, ToolSpec[Any]],
        context: object | None,
        *,
        sanitize_errors: bool,
    ) -> FunctionCallOutput:
        """Execute one tool and optionally sanitize handler failures."""
        tool = tool_by_name.get(call.name)
        if tool is None:
            if not sanitize_errors:
                raise AgentRuntimeError("unknown tool")
            return {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": "tool execution failed",
            }
        try:
            arguments = tool.parameters.model_validate_json(call.arguments)
            result = tool.handler(arguments, context)
            output = json.dumps(result, ensure_ascii=False)
        except Exception as error:
            if not sanitize_errors:
                raise AgentRuntimeError("tool execution failed") from error
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
            return self.run_structured_task(
                agent, arguments.input, context=context
            ).model_dump(mode="json")

        return ToolSpec(
            name=agent.name,
            description=agent.description,
            parameters=_SubagentArguments,
            handler=run_subagent,
        )
