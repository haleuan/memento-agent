"""Tests for conversational Agent sessions and runtime turns."""

import json
from typing import Any

import httpx
import pytest
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, StrictStr

from mementoagent.agents import (
    AgentEvent,
    AgentRuntime,
    AgentRuntimeError,
    AgentSession,
    AgentTurn,
    ToolSpec,
)


class EchoArguments(BaseModel):
    """Arguments for the session test tool."""

    model_config = ConfigDict(extra="forbid")

    value: StrictStr


class ConversationAgent:
    """Minimal conversational Agent definition used by the tests."""

    name = "conversation"
    description = "Test conversation"
    instructions = "Answer the user."
    model: str | None = None
    max_turns = 3
    max_tool_calls = 4

    def __init__(self, handler: object | None = None) -> None:
        """Initialize optional tool behavior."""
        self._handler = handler

    def tools(self) -> tuple[ToolSpec[Any], ...]:
        """Expose the optional echo tool."""
        if self._handler is None:
            return ()
        return (
            ToolSpec(
                name="echo",
                description="Echo a value.",
                parameters=EchoArguments,
                handler=self._handler,  # type: ignore[arg-type]
            ),
        )

    def subagents(self) -> tuple[Any, ...]:
        """Declare no subagents."""
        return ()


def _response(*items: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal Responses API response body."""
    return {
        "id": "resp_session",
        "object": "response",
        "created_at": 1,
        "model": "test-model",
        "status": "completed",
        "output": list(items),
    }


def _message(text: str) -> dict[str, Any]:
    """Build an assistant output message."""
    return {
        "id": "msg_session",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def _tool_call(
    arguments: str = '{"value":"ok"}',
    call_id: str = "call-session",
) -> dict[str, Any]:
    """Build an echo function call."""
    return {
        "id": "fc_session",
        "type": "function_call",
        "name": "echo",
        "arguments": arguments,
        "call_id": call_id,
        "status": "completed",
    }


def _client_factory(
    responses: list[dict[str, Any] | Exception],
) -> tuple[OpenAI, list[dict[str, Any]]]:
    """Create a real SDK client backed by an HTTP mock transport."""
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return httpx.Response(200, json=response)

    client = OpenAI(  # type: ignore[arg-type]
        api_key="test-key",
        base_url="https://model.example/v1",
        http_client=httpx.Client(  # type: ignore[arg-type]
            transport=httpx.MockTransport(handle)
        ),
        max_retries=0,
    )
    return client, requests


def test_run_turn_replays_history_and_emits_safe_events() -> None:
    """Keep prior turns in local replay state without exposing tool payloads."""
    client, requests = _client_factory(
        [
            _response(_message("first")),
            _response(_message("second")),
        ]
    )
    events: list[AgentEvent] = []
    session = AgentSession()
    runtime = AgentRuntime("test-model", client=client)

    first = runtime.run_conversation_turn(
        ConversationAgent(), session, "hello", on_event=events.append
    )
    second = runtime.run_conversation_turn(
        ConversationAgent(), session, "continue", on_event=events.append
    )

    assert first == AgentTurn(text="first")
    assert second == AgentTurn(text="second")
    assert requests[1]["input"][-1] == {
        "role": "user",
        "content": "continue",
    }
    assert requests[1]["input"][-2]["type"] == "message"
    assert requests[1]["input"][-2]["content"][0]["text"] == "first"
    assert [event.kind for event in events] == [
        "model_request",
        "model_request",
    ]
    client.close()


def test_run_turn_executes_tool_and_returns_final_text() -> None:
    """Replay a function call and its output before the final model response."""
    client, requests = _client_factory(
        [_response(_tool_call()), _response(_message("tool complete"))]
    )
    seen: list[str] = []

    def handler(arguments: EchoArguments, _context: object | None) -> str:
        seen.append(arguments.value)
        return arguments.value.upper()

    events: list[AgentEvent] = []
    runtime = AgentRuntime("test-model", client=client)
    result = runtime.run_conversation_turn(
        ConversationAgent(handler),
        AgentSession(),
        "use the tool",
        on_event=events.append,
    )

    assert result.text == "tool complete"
    assert seen == ["ok"]
    assert [event.kind for event in events] == [
        "model_request",
        "tool_call",
        "tool_result",
        "model_request",
    ]
    assert requests[1]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call-session",
        "output": '"OK"',
    }
    client.close()


def test_run_turn_sanitizes_tool_failures() -> None:
    """Return a generic tool failure without exposing handler details."""
    client, requests = _client_factory(
        [
            _response(_tool_call()),
            _response(_message("I could not complete that action.")),
        ]
    )

    def handler(_arguments: EchoArguments, _context: object | None) -> str:
        raise RuntimeError("private document and test-key")

    result = AgentRuntime("test-model", client=client).run_conversation_turn(
        ConversationAgent(handler), AgentSession(), "use the tool"
    )

    assert result.text == "I could not complete that action."
    assert requests[1]["input"][-1]["output"] == "tool execution failed"
    client.close()


def test_run_turn_enforces_agent_limits() -> None:
    """Stop a conversational turn when its per-agent request limit is reached."""
    client, _ = _client_factory([_response(_tool_call())])
    agent = ConversationAgent(lambda _arguments, _context: "ok")
    agent.max_turns = 1

    with pytest.raises(AgentRuntimeError, match="final output"):
        AgentRuntime("test-model", client=client).run_conversation_turn(
            agent, AgentSession(), "use the tool"
        )
    client.close()
