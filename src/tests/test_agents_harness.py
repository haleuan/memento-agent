"""Tests for the OpenAI Agents SDK harness boundary."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from agents import ModelProvider

from mementoagent.agents import AgentHarness, AgentHarnessError, BaseAgent
from mementoagent.agents.harness import Runner


class Output(BaseModel):
    """Structured output used by the harness tests."""

    value: str


class Task(BaseAgent[str, Output]):
    """Minimal structured task for harness tests."""

    name = "task"
    description = "A test task"
    instructions = "Return the supplied value."
    output_type = Output

    def build_input(self, value: str) -> str:
        """Build the test input."""
        return value


class RootTask(Task):
    """Task with one specialist for tool registration tests."""

    name = "root"

    def subagents(self) -> tuple[Task, ...]:
        """Return one specialist task."""
        return (Task(),)


def test_harness_returns_structured_output_and_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass task input to the SDK and return only its typed output."""
    run_sync = Mock(return_value=SimpleNamespace(final_output={"value": "ok"}))
    monkeypatch.setattr(Runner, "run_sync", run_sync)

    result = AgentHarness("test-model").run(Task(), "document text")

    assert result == Output(value="ok")
    assert run_sync.call_args.args[1] == "document text"
    assert run_sync.call_args.kwargs["max_turns"] == 1
    assert run_sync.call_args.kwargs["run_config"].tracing_disabled is True


def test_harness_passes_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pass opaque runtime context to the SDK without changing task data."""
    run_sync = Mock(return_value=SimpleNamespace(final_output=Output(value="ok")))
    monkeypatch.setattr(Runner, "run_sync", run_sync)
    context = object()

    AgentHarness("test-model").run(Task(), "input", context=context)

    assert run_sync.call_args.kwargs["context"] is context


def test_harness_accepts_an_injected_model_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use an injected SDK provider without constructing a network client."""
    run_sync = Mock(return_value=SimpleNamespace(final_output=Output(value="ok")))
    monkeypatch.setattr(Runner, "run_sync", run_sync)
    provider = Mock(spec=ModelProvider)

    AgentHarness("test-model", model_provider=provider).run(Task(), "input")

    assert run_sync.call_args.kwargs["run_config"].model_provider is provider


def test_harness_wraps_runtime_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide SDK errors behind the project harness error."""
    run_sync = Mock(side_effect=RuntimeError("secret failure"))
    monkeypatch.setattr(Runner, "run_sync", run_sync)

    with pytest.raises(AgentHarnessError, match="agent run failed") as error:
        AgentHarness("test-model", api_key="secret-key").run(Task(), "input")

    assert "secret-key" not in str(error.value)
    assert "secret failure" not in str(error.value)


def test_harness_rejects_invalid_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject output that cannot satisfy the task schema."""
    run_sync = Mock(return_value=SimpleNamespace(final_output={"wrong": 1}))
    monkeypatch.setattr(Runner, "run_sync", run_sync)

    with pytest.raises(
        AgentHarnessError,
        match="invalid structured output",
    ):
        AgentHarness("test-model").run(Task(), "input")


def test_harness_does_not_add_tools_without_subagents() -> None:
    """Build a plain SDK agent when a task has no specialists."""
    harness = AgentHarness("test-model")

    sdk_agent = harness._build_sdk_agent(Task())

    assert sdk_agent.tools == []


def test_harness_exposes_subagents_as_tools() -> None:
    """Convert declared specialists into manager-owned SDK tools."""
    harness = AgentHarness("test-model")

    sdk_agent = harness._build_sdk_agent(RootTask())

    assert len(sdk_agent.tools) == 1
    assert sdk_agent.tools[0].name == "task"
