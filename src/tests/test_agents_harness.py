"""Offline protocol tests for the project-owned Responses runtime."""

import json
from collections.abc import Callable, Iterator
from contextlib import nullcontext
from typing import Any

import httpx
import pytest
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, StrictInt

from mementoagent.agents import (
    AchievementDraft,
    AchievementExtraction,
    AchievementExtractor,
    AgentRuntime,
    AgentRuntimeError,
    BaseAgent,
    ToolSpec,
)
from mementoagent.agents import runtime as runtime_module
from mementoagent.schema import AchievementItem, ParseSnapshot, ParseSnapshotMetadata


class Output(BaseModel):
    """Structured output used by runtime tests."""

    model_config = ConfigDict(extra="forbid")

    value: str


class AddArguments(BaseModel):
    """Arguments for the test function tool."""

    model_config = ConfigDict(extra="forbid")

    value: StrictInt
    increment: StrictInt | None = None


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

    def tools(self) -> tuple[ToolSpec[AddArguments], ...]:
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

    def subagents(self) -> tuple[Specialist, ...]:
        """Return the specialist task."""
        return (Specialist(),)


ClientFactory = Callable[
    [list[dict[str, Any] | Exception]], tuple[OpenAI, list[dict[str, Any]]]
]


@pytest.fixture
def client_factory() -> Iterator[ClientFactory]:
    """Create real SDK clients backed exclusively by an HTTP mock transport."""
    clients: list[OpenAI] = []

    def make_client(
        responses: list[dict[str, Any] | Exception],
    ) -> tuple[OpenAI, list[dict[str, Any]]]:
        requests: list[dict[str, Any]] = []

        def handle(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return httpx.Response(200, json=response)

        client = OpenAI(
            api_key="test-key",
            base_url="https://model.example/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
            max_retries=0,
        )
        clients.append(client)
        return client, requests

    yield make_client
    for client in clients:
        client.close()


def response(*items: dict[str, Any]) -> dict[str, Any]:
    """Build one Responses API HTTP response body."""
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "model": "test-model",
        "status": "completed",
        "output": list(items),
    }


def message(text: str, *, phase: str | None = None) -> dict[str, Any]:
    """Build an assistant output message."""
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "phase": phase,
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def final(value: str) -> dict[str, Any]:
    """Build a final structured response."""
    return response(message(json.dumps({"value": value})))


def tool_call(
    *,
    name: str = "add_value",
    arguments: str = '{"value":2,"increment":null}',
    call_id: str = "call-1",
) -> dict[str, Any]:
    """Build one function call output item."""
    return {
        "id": "fc_" + call_id,
        "type": "function_call",
        "name": name,
        "arguments": arguments,
        "call_id": call_id,
        "status": "completed",
    }


def assert_strict_schema(schema: object) -> None:
    """Check strict object constraints throughout a transmitted JSON schema."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
        for value in schema.values():
            assert_strict_schema(value)
    elif isinstance(schema, list):
        for value in schema:
            assert_strict_schema(value)


def test_runtime_returns_structured_output_and_request_contract(client_factory) -> None:
    """Pass task fields to the real SDK and return only the typed output."""
    client, requests = client_factory([final("ok")])

    result = AgentRuntime("test-model", client=client).run(Task(), "document text")

    assert result == Output(value="ok")
    request = requests[0]
    assert request["model"] == "test-model"
    assert request["instructions"] == Task.instructions
    assert request["input"] == [{"role": "user", "content": "document text"}]
    assert "tools" not in request
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["name"] == "Output"
    assert request["text"]["format"]["strict"] is True
    assert_strict_schema(request["text"]["format"]["schema"])
    assert "api_key" not in request
    assert "base_url" not in request


def test_runtime_adapts_real_achievement_schema_and_injects_source(
    client_factory,
) -> None:
    """Adapt nested optional fields to strict schema without exposing source."""
    extraction = AchievementExtraction(
        data=AchievementItem(
            kind="award",
            title="研究生学业奖学金",
            organization="重庆师范大学",
            references=[{"type": "certificate_id", "url": "C-001"}],
        )
    )
    client, requests = client_factory([response(message(extraction.model_dump_json()))])
    snapshot = ParseSnapshot(
        metadata=ParseSnapshotMetadata(
            schema="parse/1",
            parse_id="parse_" + "b" * 32,
            source="sha256:" + "a" * 64,
            parser="test",
            parser_version="1",
            created_at="2025-01-12T09:30:00+08:00",
        ),
        content="证书标题\n重庆师范大学\n",
    )

    result = AchievementExtractor(AgentRuntime("test-model", client=client)).extract(
        snapshot
    )

    assert result == AchievementDraft(
        data=extraction.data, source=snapshot.metadata.source
    )
    schema = requests[0]["text"]["format"]["schema"]
    assert_strict_schema(schema)
    assert "description_suggestion" in schema["required"]
    assert "source" not in schema["properties"]
    assert result.data.description is None
    assert requests[0]["input"][0]["content"] == snapshot.content


def test_runtime_uses_agent_model_override(client_factory) -> None:
    """Use a task model override when it is declared."""

    class ModelTask(Task):
        model = "task-model"

    client, requests = client_factory([final("ok")])
    AgentRuntime("default-model", client=client).run(ModelTask(), "input")
    assert requests[0]["model"] == "task-model"


def test_runtime_default_is_one_model_request(client_factory) -> None:
    """Do not execute a tool when no model turn remains for its result."""
    client, requests = client_factory([response(tool_call())])

    with pytest.raises(AgentRuntimeError, match="final output"):
        AgentRuntime("test-model", client=client).run(ToolTask(), "input")

    assert len(requests) == 1


def test_runtime_replays_sdk_items_without_local_parsed_fields(client_factory) -> None:
    """Preserve message phase, reasoning and call IDs in the next HTTP request."""
    reasoning = {
        "id": "rs_test",
        "type": "reasoning",
        "summary": [],
        "encrypted_content": "opaque-reasoning",
    }
    intermediate = message('{"value":"draft"}', phase="final_answer")
    intermediate["id"] = "msg_draft"
    client, requests = client_factory(
        [
            response(
                reasoning,
                message("Working", phase="commentary"),
                intermediate,
                tool_call(),
            ),
            final("three"),
        ]
    )

    result = AgentRuntime("test-model", client=client, max_turns=2).run(
        ToolTask(), "input"
    )

    assert result == Output(value="three")
    assert len(requests) == 2
    items = requests[1]["input"]
    assert items[0] == {"role": "user", "content": "input"}
    assert items[1]["type"] == "reasoning"
    assert items[1]["encrypted_content"] == "opaque-reasoning"
    assert items[2]["phase"] == "commentary"
    assert "parsed" not in items[2]["content"][0]
    assert items[3]["phase"] == "final_answer"
    assert "parsed" not in items[3]["content"][0]
    assert items[4]["call_id"] == "call-1"
    assert "parsed_arguments" not in items[4]
    assert items[5] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "3",
    }
    tool = requests[0]["tools"][0]
    assert tool["type"] == "function"
    assert tool["strict"] is True
    assert_strict_schema(tool["parameters"])
    assert "increment" in tool["parameters"]["required"]


def test_runtime_composes_subagent_as_internal_tool(client_factory) -> None:
    """Run a declared specialist without exposing a global registry."""
    client, requests = client_factory(
        [
            response(tool_call(name="specialist", arguments='{"input":"child"}')),
            final("child result"),
            final("manager result"),
        ]
    )

    result = AgentRuntime("test-model", client=client, max_turns=2).run(
        Manager(), "parent"
    )

    assert result == Output(value="manager result")
    assert requests[0]["tools"][0]["name"] == "specialist"
    assert requests[1]["input"] == [{"role": "user", "content": "child"}]
    assert json.loads(requests[2]["input"][-1]["output"]) == {"value": "child result"}
    assert_strict_schema(requests[0]["tools"][0]["parameters"])


@pytest.mark.parametrize("arguments", ['{"input":2}', '{"input":"child","extra":1}'])
def test_runtime_rejects_invalid_subagent_arguments(client_factory, arguments) -> None:
    """Require the declared string-only subagent input contract."""
    client, _ = client_factory(
        [response(tool_call(name="specialist", arguments=arguments))]
    )
    with pytest.raises(AgentRuntimeError):
        AgentRuntime("test-model", client=client, max_turns=2).run(Manager(), "parent")


def test_runtime_passes_context_and_executes_calls_in_order(client_factory) -> None:
    """Pass run context and preserve multiple function call ordering."""
    seen: list[tuple[int, object | None]] = []

    def handler(arguments: AddArguments, context: object | None) -> int:
        seen.append((arguments.value, context))
        return arguments.value

    class ContextTask(Task):
        def tools(self) -> tuple[ToolSpec[AddArguments], ...]:
            return (ToolSpec("add_value", "Return a value.", AddArguments, handler),)

    context = object()
    client, requests = client_factory(
        [
            response(
                tool_call(arguments='{"value":1,"increment":null}', call_id="one"),
                tool_call(arguments='{"value":2,"increment":null}', call_id="two"),
            ),
            final("two"),
        ]
    )

    AgentRuntime("test-model", client=client, max_turns=2).run(
        ContextTask(), "input", context=context
    )

    assert seen == [(1, context), (2, context)]
    assert [item["call_id"] for item in requests[1]["input"][-2:]] == ["one", "two"]


@pytest.mark.parametrize(
    "payload",
    [response(), response(message("not json")), response(message('{"wrong":1}'))],
)
def test_runtime_rejects_missing_or_invalid_output(client_factory, payload) -> None:
    """Reject responses without a validated structured result."""
    client, _ = client_factory([payload])
    with pytest.raises(AgentRuntimeError):
        AgentRuntime("test-model", client=client).run(Task(), "input")


def test_runtime_wraps_model_errors_without_leaking_details(client_factory) -> None:
    """Keep underlying provider details out of the public error message."""
    client, _ = client_factory([RuntimeError("test-key and private document")])

    with pytest.raises(AgentRuntimeError, match="model request failed") as error:
        AgentRuntime("test-model", client=client).run(Task(), "private document")

    assert "test-key" not in str(error.value)
    assert "private document" not in str(error.value)


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("missing", '{"value":2,"increment":null}'),
        ("add_value", "{"),
        ("add_value", '{"value":"wrong","increment":null}'),
        ("add_value", '{"value":2,"increment":null,"extra":true}'),
    ],
)
def test_runtime_rejects_invalid_tool_calls(client_factory, name, arguments) -> None:
    """Unify unknown tools and invalid arguments under the runtime error."""
    client, _ = client_factory([response(tool_call(name=name, arguments=arguments))])
    with pytest.raises(AgentRuntimeError):
        AgentRuntime("test-model", client=client, max_turns=2).run(ToolTask(), "input")


@pytest.mark.parametrize("unserializable", [False, True])
def test_runtime_rejects_tool_handler_or_encoding_errors(
    client_factory, unserializable
) -> None:
    """Wrap execution and JSON encoding failures without exposing details."""

    def handler(arguments: AddArguments, context: object | None) -> object:
        if unserializable:
            return object()
        raise RuntimeError("private failure")

    class FailingTask(Task):
        def tools(self) -> tuple[ToolSpec[AddArguments], ...]:
            return (ToolSpec("add_value", "Fail.", AddArguments, handler),)

    client, _ = client_factory([response(tool_call())])
    with pytest.raises(AgentRuntimeError, match="tool execution failed") as error:
        AgentRuntime("test-model", client=client, max_turns=2).run(
            FailingTask(), "input"
        )
    assert "private failure" not in str(error.value)


def test_runtime_enforces_tool_call_limit(client_factory) -> None:
    """Stop before executing more calls than the configured limit."""
    client, requests = client_factory(
        [response(tool_call(call_id="one"), tool_call(call_id="two"))]
    )
    with pytest.raises(AgentRuntimeError, match="tool call limit"):
        AgentRuntime("test-model", client=client, max_turns=2, max_tool_calls=1).run(
            ToolTask(), "input"
        )
    assert len(requests) == 1


def test_runtime_supports_different_input_and_output_types(client_factory) -> None:
    """Run distinct typed tasks through the same non-generic runtime instance."""

    class Count(BaseModel):
        model_config = ConfigDict(extra="forbid")
        count: int

    class CountTask(BaseAgent[int, Count]):
        name = "count"
        description = "Count a value."
        instructions = "Return the count."
        output_type = Count

        def build_input(self, value: int) -> str:
            return str(value)

    client, requests = client_factory([final("ok"), response(message('{"count":2}'))])
    runtime = AgentRuntime("test-model", client=client)
    assert runtime.run(Task(), "input") == Output(value="ok")
    assert runtime.run(CountTask(), 2) == Count(count=2)
    assert requests[1]["text"]["format"]["name"] == "Count"
    assert requests[1]["input"][0]["content"] == "2"


@pytest.mark.parametrize("fails", [False, True])
def test_runtime_closes_owned_client_on_context_exit(
    client_factory, monkeypatch, fails
) -> None:
    """Close an internally created client on normal and exceptional scope exit."""
    client, _ = client_factory([final("ok")])
    configuration: list[dict[str, object]] = []

    def create_client(**kwargs: object) -> OpenAI:
        configuration.append(kwargs)
        return client

    monkeypatch.setattr(runtime_module, "OpenAI", create_client)
    with pytest.raises(ValueError) if fails else nullcontext():
        with AgentRuntime(
            "test-model", api_key="test-key", base_url="https://private.example/v1"
        ) as runtime:
            assert runtime.run(Task(), "input") == Output(value="ok")
            assert not client.is_closed()
            if fails:
                raise ValueError("scope failed")
    assert client.is_closed()
    assert configuration == [
        {"api_key": "test-key", "base_url": "https://private.example/v1"}
    ]


@pytest.mark.parametrize("fails", [False, True])
def test_runtime_leaves_injected_client_with_caller(client_factory, fails) -> None:
    """Preserve injected client ownership and reuse between runs."""
    client, requests = client_factory([final("first"), final("second")])
    with pytest.raises(ValueError) if fails else nullcontext():
        with AgentRuntime("test-model", client=client) as runtime:
            assert runtime.run(Task(), "one") == Output(value="first")
            assert runtime.run(Task(), "two") == Output(value="second")
            if fails:
                raise ValueError("scope failed")
    runtime.close()
    assert len(requests) == 2
    assert not client.is_closed()
