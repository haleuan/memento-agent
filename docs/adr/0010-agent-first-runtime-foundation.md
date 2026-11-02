# ADR-0010: Build the Generic Agent Runtime Before Domain Capabilities

## Status

Accepted

## Context

Memento is an Agent system whose domain capabilities happen to include
source-backed memory. The previous implementation developed the achievement
workflow and the root application harness before the generic Agent runtime was
stable. That ordering made domain-specific behavior shape the Runtime and made
the Runtime difficult to reuse for unrelated tasks.

The project needs to demonstrate the mechanisms that make an Agent useful:
model requests, tool calls, bounded continuation, multi-turn state, system
instructions, and streaming. These mechanisms must be understandable and
usable without importing Memento workspace or achievement code.

## Decision

Develop the generic Agent Runtime first using the official OpenAI Python SDK
and the Responses API.

The Runtime provides:

- one shared model/tool loop;
- `AgentDefinition`, `ToolSpec`, and `AgentSession` contracts;
- explicit structured-task and conversational-turn adapters;
- Pydantic tool argument validation and bounded execution;
- in-memory session replay;
- safe runtime events and optional Responses typed-event streaming.

The Runtime uses `responses.create()` for model requests. Structured tasks send
their Pydantic schema through Responses `text.format` and validate the final
`output_text` in the application. Conversation turns return user-visible text.

Memento capabilities are downstream consumers of this Runtime. The Runtime
must not import workspace, parser, schema, capability, or workflow modules.
CLI and TUI code remain outer adapters: deterministic slash commands are
handled by the adapter, while ordinary natural-language input is sent to an
Agent session.

## Consequences

- The Agent Loop can be understood and exercised independently of Memento.
- A second domain can reuse the same Runtime without adding a specialized
  Agent class to `agents/`.
- Domain integration is delayed until the generic execution and streaming
  contracts are stable.
- Session persistence, resume, context compression, handoffs, asynchronous
  execution, and production observability remain later Runtime work.
- README is not part of this architectural migration unless explicitly
  requested.

## Rejected alternative

Making achievement extraction the primary Runtime path would optimize the
engine around one domain and preserve the fixed-pipeline bias that this ADR is
intended to remove.
