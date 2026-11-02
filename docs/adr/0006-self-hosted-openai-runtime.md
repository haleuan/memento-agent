# ADR-0006: Own the Agent Runtime on the OpenAI Python SDK

## Status

Accepted

## Context

Memento is intended to be a usable Agent system and an inspectable example of
Agent runtime engineering. The project therefore uses the official `openai`
Python SDK for transport and Responses API types while keeping the execution
loop and application boundaries in the repository.

The runtime must support both one-shot structured capabilities and user-facing
conversational Agents. These modes have different input and output contracts,
but they must share one model/tool execution loop. Keeping two independent
loops makes tool handling, limits, error classification, and streaming behavior
drift over time.

## Decision

The local runtime owns the following boundaries:

- `AgentTask` and immutable `TaskSpec` declare one-shot structured tasks.
- `AgentDefinition` describes a conversational Agent's instructions, tools,
  limits, and optional subagents.
- `ToolSpec` declares a tool name, description, Pydantic argument model, and
  callable handler.
- `AgentRuntime.run_structured_task()` adapts a typed task to the shared loop,
  requests a Responses `text.format` JSON Schema, and validates the final
  `output_text` with the task's Pydantic output type.
- `AgentRuntime.run_conversation_turn()` adapts one user message to the same
  loop, replays local session items, dispatches tools, and returns only an
  `AgentTurn` containing user-visible text.
- Both public methods use `responses.create()`; `responses.parse()` is not part
  of the Runtime execution path.
- `AgentSession` is in-memory and scoped to one user conversation. It stores
  SDK input items internally but does not expose SDK responses to application
  code.
- `AgentEvent` exposes only safe phases, tool names, and optional user-visible
  text deltas for a future CLI or TUI; it never contains credentials, raw
  arguments, document text, or tool output.

The default runtime limit remains one model request and eight tool calls.
Conversational Agents may declare higher limits explicitly. Tool failures in a
conversation become sanitized model-readable tool results; API and Runtime
failures remain `AgentRuntimeError` failures. No automatic retry policy is
introduced.

Subagents remain a composition point rather than a global registry. Handoffs,
persistent sessions, resume, context compression, asynchronous execution,
ReAct orchestration, and production observability remain deferred.

## Consequences

- The model controls the order in which application capabilities run.
- Structured extraction remains testable as a one-shot task without becoming a
  user-facing specialized Agent.
- Conversation state and streaming events can later be rendered by a CLI, TUI,
  or web adapter without changing the Runtime loop.
- The project depends on the official OpenAI Python SDK rather than adopting a
  second Agent orchestration framework.
- Runtime changes must preserve source provenance boundaries and add an
  explicit state and failure contract before expanding execution scope.

## Rejected alternative

Using the OpenAI Agents SDK as the core runtime would provide mature loop and
tool abstractions, but would move the implementation of those mechanisms out
of this project. It remains a reference for design, not a runtime dependency.

## Future trigger

Add persistence, resume, handoffs, context management, asynchronous APIs, or
concrete subagents only when a user-facing conversation demonstrates the need
and the behavior can be covered by offline runtime tests.
