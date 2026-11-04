# ADR-0010: Build the Generic Agent Runtime Before Domain Capabilities

## Status

Accepted; updated to replace the earlier multi-adapter foundation with a
minimal concrete Agent.

## Context

Memento is an Agent system whose domain capabilities happen to include
source-backed memory. The previous implementation developed the achievement
workflow and the root application harness before the generic Agent runtime was
stable. That ordering made domain-specific behavior shape the Runtime and made
the Runtime difficult to reuse for unrelated tasks.

The first generic Runtime still combined too many mechanisms to be readily
understood. The next foundation must demonstrate only model requests, tool
calls, bounded continuation, multi-turn history, and instructions without
importing Memento workspace or achievement code.

## Decision

Develop the generic Agent Runtime first using the official OpenAI Python SDK
and the Responses API.

The package is layered by current responsibility: `runtime/` contains `Agent`
and `Tool`, while `conversation/` contains `Conversation`. The package root
exports `Agent`, `Tool`, `ToolError`, and `Conversation`. `Agent.run()` contains
one synchronous Responses API tool loop and returns text. The caller passes an
explicit Conversation to each run; it retains complete local replay history,
including model output items and tool results. History is private to the
Conversation and can be cleared with `clear()`. Pydantic is used only for tool
arguments. The caller owns the OpenAI client.

`Tool.definition()` uses the SDK's Pydantic Responses declaration helper.
`Tool.execute()` validates JSON arguments, invokes the handler, and serializes
the result. Argument validation errors and explicit `ToolError` messages are
returned as model-visible tool outputs; unexpected handler errors produce a
generic output without exception details. `Agent.run()` sends model requests,
appends every output item, dispatches function calls, and appends
`function_call_output` items with their `call_id`. Unknown tool names also
produce a model-visible error output. The default limit is eight model
requests per call. If a request limit is reached before a final response,
`run()` raises `RuntimeError` without executing tool calls from that last
response. Non-completed responses fail without committing the Conversation.
API errors propagate after the SDK's configured retries. Tool side effects
already performed are not rolled back.

The loop replays native reasoning and function-call items unchanged, rather
than imposing the SDK `ResponsesToolRunner`'s additional native-reasoning shape
validation. Conversation history is committed only after a completed final
response. A failed turn is not retained, even if a tool side effect already
occurred; callers must account for that before retrying non-idempotent
operations.

Remove the earlier Runtime, task declarations and protocols, structured output
adapter, events, streaming, subagents, and generic context injection. Use an
explicit in-memory Conversation for history, without persistence or resume. Do
not preserve removed APIs through compatibility wrappers or a legacy package.

Memento capabilities consume this Agent through an application harness. The
Agent still must not import workspace, parser, schema, capability, or workflow
modules. `Agent.run_structured()` is a one-shot, no-tools, no-history adapter
for Pydantic extraction; capability modules own their prompts and output
models, while the Agent owns the SDK request and validation boundary. CLI and
TUI code remain outer adapters: deterministic slash commands are handled by
the adapter, while ordinary natural-language input is sent to an Agent.

## Consequences

- The Agent Loop can be understood and exercised independently of Memento.
- Ordinary functions or bound methods supply tool dependencies without a
  generic context mechanism or specialized Agent subclasses.
- The first achievement vertical slice can be assembled without importing
  Memento code into `agents/`; its line-oriented `memento chat` adapter remains
  outside the generic package.
- Streaming, conversation persistence, resume, context compression, handoffs,
  asynchronous execution, and observability remain later work, introduced only
  for concrete needs.
- README is not part of this architectural migration unless explicitly
  requested.

## Rejected alternative

Making achievement extraction the primary Runtime path would optimize the
engine around one domain and preserve the fixed-pipeline bias that this ADR is
intended to remove.
