"""Regression tests for generic task contracts and package boundaries."""

import ast
import json
from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import OpenAI
from pydantic import BaseModel, ConfigDict

from mementoagent import agents
from mementoagent.agents import AgentRuntime, AgentTask, TaskSpec, ToolSpec


class Output(BaseModel):
    """Output for a structurally defined task."""

    model_config = ConfigDict(extra="forbid")

    value: str


class StructuralTask:
    """Implement the task protocol without inheritance or TaskSpec."""

    name = "structural_task"
    description = "Return the supplied value."
    instructions = "Return a structured value."
    output_type = Output
    model: str | None = None

    def build_input(self, value: str) -> str:
        """Convert input without a task-specific base class."""
        return value

    def tools(self) -> Sequence[ToolSpec[Any]]:
        """Declare no function tools."""
        return ()

    def subagents(self) -> Sequence[AgentTask[str, Any]]:
        """Declare no specialist tasks."""
        return ()


def test_task_spec_is_immutable() -> None:
    """Prevent shared task declarations from being changed between runs."""
    task = TaskSpec(
        name="task",
        description="A structured task.",
        instructions="Return a value.",
        output_type=Output,
        input_builder=str,
    )

    with pytest.raises(FrozenInstanceError):
        setattr(task, "instructions", "Changed instructions.")


def test_runtime_accepts_a_structurally_compatible_task() -> None:
    """Execute an independent protocol implementation through the runtime."""
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        """Return an offline structured response."""
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "resp_structural",
                "object": "response",
                "created_at": 1,
                "model": "test-model",
                "status": "completed",
                "output": [
                    {
                        "id": "msg_structural",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"value": "result"}',
                                "annotations": [],
                            }
                        ],
                    }
                ],
            },
        )

    task: AgentTask[str, Output] = StructuralTask()
    with httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
        with OpenAI(api_key="test-key", http_client=http_client) as client:
            result = AgentRuntime("test-model", client=client).run_structured_task(
                task, "input"
            )

    assert result == Output(value="result")
    assert requests[0]["instructions"] == task.instructions
    assert requests[0]["input"] == [{"role": "user", "content": "input"}]


def test_agents_exports_only_generic_interfaces() -> None:
    """Keep achievement workflows out of the generic package API."""
    assert set(agents.__all__) == {
        "AgentRuntime",
        "AgentRuntimeError",
        "AgentStructuredOutputError",
        "AgentDefinition",
        "AgentEvent",
        "AgentSession",
        "AgentTask",
        "TaskSpec",
        "AgentTurn",
        "ToolSpec",
    }
    assert not any("Achievement" in name for name in vars(agents))
    assert not hasattr(agents, "BaseAgent")


def test_agents_do_not_import_workflows_or_domain_schema() -> None:
    """Preserve the dependency direction from workflows to generic agents."""
    package_dir = Path(agents.__file__).parent
    forbidden = {"workflows", "schema"}

    for path in package_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not forbidden.intersection(alias.name.split(".")), path
            elif isinstance(node, ast.ImportFrom):
                module_parts = (node.module or "").split(".")
                assert not forbidden.intersection(module_parts), path
                if node.level >= 2 or node.module == "mementoagent":
                    assert not forbidden.intersection(
                        alias.name for alias in node.names
                    ), path
