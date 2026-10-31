"""OpenAI Agents SDK runtime boundary for Memento agents."""

from typing import Any, cast

from agents import Agent, ModelProvider, OpenAIProvider, RunConfig, Runner, Tool
from pydantic import ValidationError

from .base import BaseAgent, InputT, OutputT


class AgentHarnessError(RuntimeError):
    """Raised when the agent runtime cannot produce structured output."""


class AgentHarness:
    """Run Memento task agents through the OpenAI Agents SDK."""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_provider: ModelProvider | None = None,
        max_turns: int = 1,
    ) -> None:
        """Initialize the runtime configuration.

        Args:
            model: Default model used by tasks without a model override.
            api_key: Optional API key passed to the SDK provider.
            base_url: Optional OpenAI-compatible endpoint passed to the SDK provider.
            model_provider: Optional SDK provider used by tests or custom runtimes.
            max_turns: Maximum model turns for one run. Defaults to one.
        """
        self._model = model
        self._model_provider = model_provider or OpenAIProvider(
            api_key=api_key,
            base_url=base_url,
        )
        self._max_turns = max_turns

    def run(
        self,
        agent: BaseAgent[InputT, OutputT],
        value: InputT,
        *,
        context: object | None = None,
    ) -> OutputT:
        """Run one task and return only its validated structured output.

        Args:
            agent: Task declaration to execute.
            value: Domain input for the task.
            context: Optional runtime context passed to the SDK.

        Returns:
            The task's validated Pydantic output.

        Raises:
            AgentHarnessError: If the SDK run or output validation fails.
        """
        sdk_agent = self._build_sdk_agent(agent)
        run_config = RunConfig(
            model_provider=self._model_provider,
            tracing_disabled=True,
        )
        try:
            result = Runner.run_sync(
                sdk_agent,
                agent.build_input(value),
                context=context,
                max_turns=self._max_turns,
                run_config=run_config,
            )
        except Exception as error:
            raise AgentHarnessError("agent run failed") from error

        try:
            output = result.final_output
            if isinstance(output, agent.output_type):
                return output
            return cast(OutputT, agent.output_type.model_validate(output))
        except (TypeError, ValidationError) as error:
            raise AgentHarnessError(
                "agent returned invalid structured output"
            ) from error

    def _build_sdk_agent(
        self,
        agent: BaseAgent[Any, Any],
    ) -> Agent[Any]:
        tools: list[Tool] = []
        for subagent in agent.subagents():
            tools.append(
                self._build_sdk_agent(subagent).as_tool(
                    tool_name=subagent.name,
                    tool_description=subagent.description,
                    max_turns=self._max_turns,
                    run_config=RunConfig(
                        model_provider=self._model_provider,
                        tracing_disabled=True,
                    ),
                )
            )
        return Agent(
            name=agent.name,
            instructions=agent.instructions,
            handoff_description=agent.description,
            tools=tools,
            model=agent.model or self._model,
            output_type=agent.output_type,
        )
