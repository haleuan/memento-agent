# ADR-0006: Own the Agent Runtime on the OpenAI Python SDK

## Status

Accepted

## Context

Memento is intended to be a usable Agent system and an inspectable example of
Agent runtime engineering. The previous Harness delegated the model loop,
structured output handling, and tool composition to the OpenAI Agents SDK.
That reduced local code, but it also hid the execution mechanisms that this
project needs to make explicit and evolve deliberately.

The current workflow needs only synchronous Responses API calls, typed task
outputs, and a bounded function-tool loop. It does not yet need sessions,
handoffs, ReAct orchestration, durable state, or asynchronous execution.

## Decision

Use the official `openai` Python SDK for transport and Responses API types, and
keep the Agent runtime in Memento. The runtime owns the following boundaries:

- `BaseAgent` declares task instructions, input conversion, output type, and
  optional tools or composable subagents.
- `ToolSpec` explicitly declares a tool name, description, Pydantic argument
  model, and callable handler.
- `AgentRuntime` creates or accepts an OpenAI client and owns the Responses
  request loop, tool dispatch, execution limits, and output/error boundaries.
- The SDK's `responses.parse()` and public Pydantic tool helper adapt schemas
  to the Responses protocol and parse typed results. The Runtime replays SDK
  output items through the SDK serializer, including tool call identifiers and
  reasoning items, without adding SDK-only parsed fields to request payloads.
- `RunState` is in-memory and scoped to one invocation. The public runtime API
  returns only the task's validated output, not SDK responses, usage, or traces.

`max_turns` counts model requests and defaults to one. Tasks that use tools
must opt into additional model requests. Tool calls are capped independently
by `max_tool_calls`, and invalid tool names, arguments, handler failures, or
non-serializable results terminate the run through one runtime error boundary.

Subagents remain a composition point rather than a global registry. A manager
may expose a bounded subagent as an internal tool; handoffs and concrete
subagent implementations are deferred until a real task requires them.

## Consequences

- The core request and tool execution path is visible, testable, and owned by
  the project.
- The project depends on the stable OpenAI Python SDK rather than adopting a
  second Agent orchestration framework as a core dependency.
- The first implementation has a deliberately narrow synchronous scope. It
  does not provide sessions, context compression, resume, handoffs, ReAct,
  asynchronous execution, or production trace/usage observability.
- Future runtime changes must preserve source provenance boundaries and must
  add an explicit state and failure contract before expanding execution scope.

## Rejected alternative

Using the OpenAI Agents SDK as the core runtime would provide mature loop and
tool abstractions, but would move the implementation of those mechanisms out
of this project. It remains a possible reference for future design, not a
runtime dependency.

## Future trigger

Add sessions, durable state, handoffs, context management, asynchronous APIs,
or concrete subagents only when a user-facing workflow demonstrates the need
and the behavior can be covered by offline runtime tests.
