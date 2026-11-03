# ADR-0006: Own the Agent Runtime on the OpenAI Python SDK

## Status

Accepted; the manually implemented loop and replay-history policy below are
superseded by the manual Responses API loop and message-history policy in
[ADR-0010](0010-agent-first-runtime-foundation.md).

## Context

Memento is intended to be a usable Agent system and an inspectable example of
Agent runtime engineering. The project therefore uses the official `openai`
Python SDK for transport and Responses API types while keeping the execution
loop and application boundaries in the repository.

The earlier Runtime combined structured tasks, conversations, streaming,
subagents, context injection, and client lifecycle management. Its overlapping
protocols and adapters obscured the basic tool loop. The current priority is to
make the complete implementation understandable before adding capabilities.

## Decision

- `agents/` exports only concrete `Agent` and `Tool` types.
- `Agent.run(user_input)` contains one synchronous `responses.create()` loop
  and returns final text. The Agent retains its own in-memory conversation.
- `Tool` declares a name, description, Pydantic argument model, and handler
  accepting only validated arguments. The SDK helper generates its schema.
- Every model output item is replayed, including reasoning items. Tool results
  use `function_call_output` with the matching `call_id`.
- Each invocation works on a copy of the history and commits it only after a
  final response. Failures do not commit partial history or undo tool effects.
- `max_model_calls` defaults to eight per invocation. Exhaustion raises
  `RuntimeError`; API, argument validation, and handler exceptions propagate.
- The caller creates and closes the SDK client. Agent code does not construct
  clients, read credentials, or own transport configuration.

There are no Runtime/task protocols, compatibility wrappers, structured final
output adapters, separate Sessions, events, streaming, subagents, or generic
context injection. These can be reconsidered individually after the minimal
loop is understood.

## Consequences

- The model controls the order in which application capabilities run.
- The complete execution path is readable in `Tool` and `Agent.run()`.
- Existing Memento extraction and application integration are retained but
  paused; they still reference deleted APIs. Package initializers no longer
  import those modules automatically.
- Deterministic materialization, workspace I/O, parsers, validation, and the
  check CLI remain independent and usable.
- The project depends on the official OpenAI Python SDK rather than adopting a
  second Agent orchestration framework.
- Domain provenance remains the responsibility of later integration, not the
  generic Agent loop.

## Rejected alternative

Using the OpenAI Agents SDK as the core runtime would provide mature loop and
tool abstractions, but would move the implementation of those mechanisms out
of this project. It remains a reference for design, not a runtime dependency.

## Future trigger

Add features individually when the minimal loop is understood and a concrete
use requires them. New or expanded tests require explicit user approval.
