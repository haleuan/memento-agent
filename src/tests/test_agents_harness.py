"""Tests for the project-owned OpenAI Responses runtime."""

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from mementoagent.agents import BaseAgent
from mementoagent.agents.runtime import AgentRuntime, AgentRuntimeError
from mementoagent.agents.tools import ToolSpec


class Output(BaseModel):
    """Structured output used by runtime tests."""

    value: str


class AddArguments(BaseModel):
    """Arguments for the test function tool."""

    value: int


class Task(BaseAgent[str, Output]):
    """Minimal structured task."""

    name = "task"
    description = "A test task"
    instructions = "Return the supplied value."
    output_type = Output

    def build_input(self, value: str) -> str:
        """Build the test input."""
        return value


class ToolTask(Task):
    """Task exposing one explicit function tool."""

    name = "tool_task"

    def tools(self) -> tuple[ToolSpec, ...]:
        """Return the test tool."""
        return (
            ToolSpec(
                name="add_value",
                description="Add one value.",
                parameters=AddArguments,
                handler=lambda arguments, _context: arguments.value + 1,
            ),
        )


class Specialist(Task):
    """Specialist task used to verify subagent composition."""

    name = "specialist"
    description = "Run the specialist task."


class Manager(Task):
    """Manager task exposing a specialist as an internal tool."""

    name = "manager"

    def subagents(self) -> tuple[BaseAgent[Any, Any], ...]:
        """Return the specialist task."""
        return (Specialist(),)


@dataclass
class FakeResponse:
    """Small Responses API response substitute."""

    output: list[Any]
    output_text: str = ""


class FakeResponses:
    """Record requests and return configured responses in order."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        """Initialize configured responses."""
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        """Record one request and return the next fake response."""
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected model request")
        return self.responses.pop(0)


class FakeClient:
    """Fake OpenAI client exposing the Responses resource."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        """Initialize the fake responses resource."""
        self.responses = FakeResponses(responses)


def final(value: str) -> FakeResponse:
    """Build a final structured response."""
    return FakeResponse(output=[], output_text=json.dumps({"value": value}))


def tool_call(
    *,
    name: str = "add_value",
    arguments: str = '{"value": 2}',
    call_id: str = "call-1",
) -> FakeResponse:
    """Build a response containing one function call."""
    return FakeResponse(
        output=[
            SimpleNamespace(
                type="function_call",
                name=name,
                arguments=arguments,
                call_id=call_id,
            )
        ]
    )


def test_runtime_returns_structured_output_and_request_contract() -> None:
    """Pass task fields to Responses and return only the typed output."""
    client = FakeClient([final("ok")])

    result = AgentRuntime("test-model", client=client).run(Task(), "document text")

    assert result == Output(value="ok")
    request = client.responses.calls[0]
    assert request["model"] == "test-model"
    assert request["instructions"] == Task.instructions
    assert request["input"] == "document text"
    assert "tools" not in request
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["name"] == "Output"
    assert request["text"]["format"]["strict"] is True


def test_runtime_uses_agent_model_override() -> None:
    """Use a task model override when it is declared."""
    client = FakeClient([final("ok")])

    class ModelTask(Task):
        model = "task-model"

    AgentRuntime("default-model", client=client).run(ModelTask(), "input")

    assert client.responses.calls[0]["model"] == "task-model"


def test_runtime_default_is_one_model_request() -> None:
    """Do not continue a tool loop when the default limit is one."""
    client = FakeClient([tool_call()])

    with pytest.raises(AgentRuntimeError, match="final output"):
        AgentRuntime("test-model", client=client).run(ToolTask(), "input")

    assert len(client.responses.calls) == 1


def test_runtime_executes_bounded_tool_loop() -> None:
    """Return tool output to the model and parse the next final response."""
    client = FakeClient([tool_call(), final("three")])

    result = AgentRuntime("test-model", client=client, max_turns=2).run(
        ToolTask(), "input", context={"request_id": "r1"}
    )

    assert result == Output(value="three")
    assert len(client.responses.calls) == 2
    second_input = client.responses.calls[1]["input"]
    assert second_input[-1]["type"] == "function_call_output"
    assert second_input[-1]["call_id"] == "call-1"
    assert second_input[-1]["output"] == "3"


def test_runtime_composes_subagent_as_internal_tool() -> None:
    """Run a declared specialist without exposing a global registry."""
    client = FakeClient(
        [
            tool_call(name="specialist", arguments='{"input":"child"}'),
            final("child result"),
            final("manager result"),
        ]
    )

    result = AgentRuntime("test-model", client=client, max_turns=2).run(
        Manager(), "parent"
    )

    assert result == Output(value="manager result")
    assert client.responses.calls[0]["tools"][0]["name"] == "specialist"
    assert client.responses.calls[1]["input"] == "child"


def test_runtime_passes_context_to_tool() -> None:
    """Pass opaque context to a tool handler."""
    seen: list[object | None] = []

    def handler(arguments: AddArguments, context: object | None) -> int:
        seen.append(context)
        return arguments.value

    task = ToolTask()
    task.tools = lambda: (
        ToolSpec(
            name="add_value",
            description="Add one value.",
            parameters=AddArguments,
            handler=handler,
        ),
    )  # type: ignore[method-assign]
    client = FakeClient([tool_call(), final("two")])
    context = object()

    AgentRuntime("test-model", client=client, max_turns=2).run(
        task, "input", context=context
    )

    assert seen == [context]


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse(output=[], output_text=""), "structured output"),
        (FakeResponse(output=[], output_text="not json"), "structured output"),
    ],
)
def test_runtime_rejects_missing_or_invalid_output(
    response: FakeResponse, message: str
) -> None:
    """Reject responses without valid structured output."""
    with pytest.raises(AgentRuntimeError, match=message):
        AgentRuntime("test-model", client=FakeClient([response])).run(Task(), "input")


def test_runtime_wraps_model_errors_without_leaking_details() -> None:
    """Hide provider exception text and credentials behind one error."""

    class FailingResponses(FakeResponses):
        def create(self, **kwargs: Any) -> FakeResponse:
            raise RuntimeError("secret-key and private document")

    client = FakeClient([])
    client.responses = FailingResponses([])

    with pytest.raises(AgentRuntimeError, match="model request failed") as error:
        AgentRuntime("test-model", client=client, api_key="secret-key").run(
            Task(), "private document"
        )

    assert "secret-key" not in str(error.value)
    assert "private document" not in str(error.value)


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("missing", '{"value": 2}', "unknown tool"),
        ("add_value", "{", "tool execution failed"),
        ("add_value", '{"value":"wrong"}', "tool execution failed"),
    ],
)
def test_runtime_rejects_invalid_tool_calls(
    name: str, arguments: str, message: str
) -> None:
    """Fail closed for unknown tools and invalid tool arguments."""
    client = FakeClient([tool_call(name=name, arguments=arguments)])

    with pytest.raises(AgentRuntimeError, match=message):
        AgentRuntime("test-model", client=client, max_turns=2).run(ToolTask(), "input")


def test_runtime_rejects_tool_handler_errors() -> None:
    """Convert handler failures to the runtime error boundary."""

    class FailingTask(ToolTask):
        def tools(self) -> tuple[ToolSpec, ...]:
            return (
                ToolSpec(
                    name="add_value",
                    description="Fail.",
                    parameters=AddArguments,
                    handler=lambda _arguments, _context: (_ for _ in ()).throw(
                        RuntimeError("private failure")
                    ),
                ),
            )

    with pytest.raises(AgentRuntimeError, match="tool execution failed") as error:
        AgentRuntime("test-model", client=FakeClient([tool_call()]), max_turns=2).run(
            FailingTask(), "input"
        )

    assert "private failure" not in str(error.value)


def test_runtime_rejects_non_serializable_tool_result() -> None:
    """Reject a tool result that cannot be encoded as JSON."""

    class UnserializableTask(ToolTask):
        def tools(self) -> tuple[ToolSpec, ...]:
            return (
                ToolSpec(
                    name="add_value",
                    description="Return an unserializable value.",
                    parameters=AddArguments,
                    handler=lambda _arguments, _context: object(),
                ),
            )

    with pytest.raises(AgentRuntimeError, match="tool execution failed"):
        AgentRuntime("test-model", client=FakeClient([tool_call()]), max_turns=2).run(
            UnserializableTask(), "input"
        )


def test_runtime_enforces_tool_call_limit() -> None:
    """Stop before executing more calls than the configured limit."""
    response = FakeResponse(
        output=[
            SimpleNamespace(
                type="function_call",
                name="add_value",
                arguments='{"value": 1}',
                call_id="one",
            ),
            SimpleNamespace(
                type="function_call",
                name="add_value",
                arguments='{"value": 2}',
                call_id="two",
            ),
        ]
    )

    with pytest.raises(AgentRuntimeError, match="tool call limit"):
        AgentRuntime(
            "test-model", client=FakeClient([response]), max_turns=2, max_tool_calls=1
        ).run(ToolTask(), "input")


def test_runtime_accepts_injected_client_and_base_url_without_request_leak() -> None:
    """Use an injected client and keep configuration out of request payloads."""
    client = FakeClient([final("ok")])

    AgentRuntime(
        "test-model", client=client, api_key="secret-key", base_url="https://private"
    ).run(Task(), "input")

    request = client.responses.calls[0]
    assert "api_key" not in request
    assert "base_url" not in request
