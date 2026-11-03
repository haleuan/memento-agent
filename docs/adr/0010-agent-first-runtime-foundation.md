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

The package contains only `__init__.py`, `agent.py`, and `tools.py`, and exports
`Agent` and `Tool`. `Agent.run()` contains the complete synchronous Responses
tool loop and returns text. Each instance retains its own history. Pydantic is
used only for tool arguments. The caller owns the OpenAI client.

`Tool.definition()` generates its API declaration with the SDK helper.
`Tool.execute()` validates JSON arguments, invokes the handler, and serializes
the result as JSON. `Agent.run()` retains model requests, tool lookup,
`call_id` result envelopes, and history management. Tool declarations and the
lookup map are rebuilt for each call without caching or additional layers.

The default request limit is eight per call. API and tool exceptions propagate;
limit exhaustion raises `RuntimeError`. History is committed only on success,
without rolling back already executed tool effects.

Remove the earlier Runtime, task declarations and protocols, structured output
adapter, standalone Session, events, streaming, subagents, and context injection.
Do not preserve them through compatibility wrappers or a legacy package.

Memento capabilities are future downstream consumers of this Agent. The Agent
must not import workspace, parser, schema, capability, or workflow modules.
CLI and TUI code remain outer adapters: deterministic slash commands are
handled by the adapter, while ordinary natural-language input is sent to an
Agent. The retained extraction, harness, and workflow tools are temporarily
incompatible with the new API; package initializers must not eagerly import
them. Deterministic domain modules remain usable.

## Consequences

- The Agent Loop can be understood and exercised independently of Memento.
- Ordinary functions or bound methods supply tool dependencies without a
  generic context mechanism or specialized Agent subclasses.
- Domain integration is paused until the minimal loop is understood. Old
  integration tests remain unchanged and are excluded from scoped checks;
  full-project validation is not claimed.
- Structured output, streaming, session persistence, resume, context
  compression, handoffs, asynchronous execution, and observability remain
  later work, introduced only for concrete needs.
- README is not part of this architectural migration unless explicitly
  requested.

## Rejected alternative

Making achievement extraction the primary Runtime path would optimize the
engine around one domain and preserve the fixed-pipeline bias that this ADR is
intended to remove.
